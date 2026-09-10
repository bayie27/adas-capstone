"""GPU-resident NV12 -> grayscale-letterbox preprocessing.

Ported from the throwaway `prototypes/prototype_exact_gpu.py`. The CUDA kernel below is
copied VERBATIM from that prototype — it is the arithmetic reference, and
ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 5.1 is explicit that it must not be
"improved": it deliberately reproduces, bit for bit, what the current
software stack already does (FFmpeg 4.4's fixed-point BT.601 YUV->RGB,
OpenCV's fixed-point grayscale weights, OpenCV 4.13's fixed-point bilinear
resize) so that switching readers changes no detection. A generic bilinear
resize or the decoder's own RGB conversion was tried first and failed the
17-clip accuracy gate.

Only two things changed from the prototype: the hardcoded compute capability
and the Windows-only NVRTC/driver loading are now resolved at runtime instead
of hardcoded, per section 5.2.
"""

import ctypes as ct
import ctypes.util
import json
import platform
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

# Verbatim from prototypes/prototype_exact_gpu.py — do not edit this arithmetic without
# new accuracy-gate evidence (see the module docstring above).
SOURCE = r"""
__device__ int gray_at(const unsigned char* p, int pitch, int h, int x, int y, int full) {
    int yy = full ? (int)p[y*pitch+x] : ((((int)p[y*pitch+x]*8-128)*9539)>>16);
    int offset = h*pitch+(y/2)*pitch+(x/2)*2;
    int u = ((int)p[offset]-128)*8, v = ((int)p[offset+1]-128)*8;
    int b = yy + ((u*(full?14516:16525))>>16);
    int g = yy + ((u*(full?-2819:-3209))>>16) + ((v*(full?-5850:-6660))>>16);
    int r = yy + ((v*(full?11485:13075))>>16);
    b = b<0?0:(b>255?255:b); g = g<0?0:(g>255?255:g); r = r<0?0:(r>255?255:r);
    return (r*9798+g*19235+b*3735+16384)>>15;
}
extern "C" __global__ void prep(const unsigned char* p, unsigned char* out,
    const int* xs, const int* ys, int pitch, int h, int oh, int ow,
    int rh, int rw, int top, int left, int full) {
    int i = blockIdx.x*blockDim.x+threadIdx.x;
    if(i>=oh*ow) return;
    int x=i%ow-left, y=i/ow-top, value=114;
    if(x>=0 && x<rw && y>=0 && y<rh) {
        int x0=xs[x*4], x1=xs[x*4+1], a0=xs[x*4+2], a1=xs[x*4+3];
        int y0=ys[y*4], y1=ys[y*4+1], b0=ys[y*4+2], b1=ys[y*4+3];
        int s0=gray_at(p,pitch,h,x0,y0,full)*a0+gray_at(p,pitch,h,x1,y0,full)*a1;
        int s1=gray_at(p,pitch,h,x0,y1,full)*a0+gray_at(p,pitch,h,x1,y1,full)*a1;
        int t0=(b0*(s0>>4))>>16, t1=(b1*(s1>>4))>>16;
        value=(t0+t1+2)>>2;
    }
    out[i]=value; out[i+oh*ow]=value; out[i+2*oh*ow]=value;
}
"""


class UnsupportedFrameError(RuntimeError):
    """A live stream's format, device or driver falls outside what this
    kernel was built and validated for. Raised instead of guessing, per
    ai_engine/docs/AI_ENGINE_GPU_INTEGRATION_PLAN.md section 6.2: an unsupported format must
    never silently feed an incorrect tensor.
    """


def check(status):
    if status:
        raise RuntimeError(f"CUDA/NVRTC error {status}")


def _compute_capability() -> bytes:
    """Was hardcoded to `compute_86` in the prototype (section 5.2). Queried
    from the actual device via torch, which already exposes it — no need to
    shell out or parse nvidia-smi.
    """
    major, minor = torch.cuda.get_device_capability()
    return f"compute_{major}{minor}".encode()


def _find_nvrtc_library() -> Path:
    """The prototype hardcoded `nvrtc64_130_0.dll` (Windows only, and tied to
    one CUDA minor version). Torch ships NVRTC for its own JIT under
    `<torch>/lib`, keyed by whatever CUDA version this build was compiled
    against, so glob for it instead of hardcoding the version string.
    """
    lib_dir = Path(torch.__file__).resolve().parent / "lib"
    if platform.system() == "Windows":
        candidates = sorted(
            p for p in lib_dir.glob("nvrtc64_*_0.dll") if ".alt." not in p.name
        )
    else:
        candidates = sorted(lib_dir.glob("libnvrtc.so*"))
    if not candidates:
        raise UnsupportedFrameError(
            f"No NVRTC library found under {lib_dir}. GPU decode needs the "
            "CUDA-enabled torch build the `ai` extra installs; a CPU-only "
            "torch has no bundled NVRTC."
        )
    return candidates[0]


def _load_nvrtc():
    library = _find_nvrtc_library()
    if platform.system() == "Windows":
        return ct.WinDLL(str(library))
    return ct.CDLL(str(library))


def _load_driver():
    if platform.system() == "Windows":
        return ct.WinDLL("nvcuda.dll")
    name = ctypes.util.find_library("cuda") or "libcuda.so.1"
    return ct.CDLL(name)


@lru_cache(maxsize=1)
def kernel():
    """Compiles the kernel once per process and caches the driver/module/
    function handles. Call eagerly at startup (see gpu_camera.validate_gpu_
    support()) so a compile failure is a loud startup error, not a surprise
    on the first frame.
    """
    if not torch.cuda.is_available():
        raise UnsupportedFrameError(
            "AI_GPU_DECODE=1 but torch.cuda.is_available() is False."
        )
    # torch.cuda.init() alone does not reliably leave a context current for
    # the raw driver API below (cuModuleLoadData) to find — confirmed by
    # direct testing: it fails with CUDA_ERROR_INVALID_CONTEXT (201) unless
    # an actual tensor allocation has happened first. A real allocation is
    # what torch's caching allocator uses to lazily create and bind the
    # primary context, so force that instead of relying on init() alone.
    torch.cuda.init()
    torch.zeros(1, device="cuda")
    rtc = _load_nvrtc()
    program = ct.c_void_p()
    check(
        rtc.nvrtcCreateProgram(
            ct.byref(program), SOURCE.encode(), b"gpu_preprocess.cu", 0, None, None
        )
    )
    options = (ct.c_char_p * 1)(b"--gpu-architecture=" + _compute_capability())
    result = rtc.nvrtcCompileProgram(program, 1, options)
    if result:
        size = ct.c_size_t()
        rtc.nvrtcGetProgramLogSize(program, ct.byref(size))
        log = ct.create_string_buffer(size.value)
        rtc.nvrtcGetProgramLog(program, log)
        raise UnsupportedFrameError(
            f"CUDA kernel failed to compile for this device: {log.value.decode()}"
        )
    size = ct.c_size_t()
    check(rtc.nvrtcGetPTXSize(program, ct.byref(size)))
    ptx = ct.create_string_buffer(size.value)
    check(rtc.nvrtcGetPTX(program, ptx))
    check(rtc.nvrtcDestroyProgram(ct.byref(program)))
    driver = _load_driver()
    module, function = ct.c_void_p(), ct.c_void_p()
    check(driver.cuModuleLoadData(ct.byref(module), ptx))
    check(driver.cuModuleGetFunction(ct.byref(function), module, b"prep"))
    return driver, module, function


@lru_cache(maxsize=64)
def _axis(source, destination):
    """Verbatim resize-axis arithmetic from the prototype's `axis()` —
    OpenCV 4.13's fixed-point bilinear coefficients. Unchanged."""
    coordinate = (
        (np.arange(destination, dtype=np.float64) + 0.5) * (source / destination) - 0.5
    ).astype(np.float32)
    first = np.floor(coordinate).astype(np.int32)
    fraction = coordinate - first
    fraction[(first < 0) | (first >= source - 1)] = 0
    first = np.clip(first, 0, source - 1)
    second = np.minimum(first + 1, source - 1)
    weights0 = np.rint((1 - fraction) * 2048).astype(np.int32)
    weights1 = np.rint(fraction * 2048).astype(np.int32)
    return torch.from_numpy(np.stack([first, second, weights0, weights1], axis=1)).to(
        "cuda"
    )


_SUPPORTED_PIX_FMTS = {"yuv420p", "yuvj420p"}


def source_full_range(source: str, *, ffprobe_timeout: float = 5.0) -> bool:
    """Limited/full-range colour metadata, read from the LIVE source.

    Generalises the prototype's `source_full_range()`, which only accepted a
    fixture file path. ffprobe reads a network stream (rtsp://...) exactly
    the same way it reads a file, which is what a live camera needs — there
    is no file path for an RTSP source (section 5.2). TCP transport matches
    what the rest of this engine forces for RTSP (config.py,
    OPENCV_FFMPEG_CAPTURE_OPTIONS); it is a no-op for a plain file path.

    Raises UnsupportedFrameError for any pixel format this kernel was not
    built for, rather than defaulting to limited range and silently shifting
    colours.
    """
    command = ["ffprobe", "-v", "error"]
    if str(source).startswith("rtsp://"):
        command += ["-rtsp_transport", "tcp"]
    command += [
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=pix_fmt,color_range",
        "-of",
        "json",
        str(source),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=True,
        timeout=ffprobe_timeout,
        creationflags=subprocess.CREATE_NO_WINDOW
        if platform.system() == "Windows"
        else 0,
    )
    streams = json.loads(result.stdout).get("streams") or []
    if not streams:
        raise UnsupportedFrameError(f"ffprobe found no video stream on {source!r}")
    metadata = streams[0]
    if metadata.get("pix_fmt") not in _SUPPORTED_PIX_FMTS:
        raise UnsupportedFrameError(
            f"Unsupported pixel format for GPU decode: {metadata!r}"
        )
    return metadata.get("color_range") == "pc" or metadata["pix_fmt"] == "yuvj420p"


def prepare_nv12(
    native: torch.Tensor,
    *,
    square: bool,
    dtype: torch.dtype,
    full_range: bool,
) -> torch.Tensor:
    """NV12 device tensor -> one prepared (1, 3, imgsz, imgsz-or-rect) model
    input tensor, computing only the source pixels the resized output needs.

    `square` selects square vs. stride-aligned rectangular padding and MUST
    be computed by the caller from the actual batch, every tick — see
    detector._letterbox_auto_for_shapes(). This module never caches it.

    Verbatim arithmetic from prototypes/prototype_exact_gpu.py's `prepare_nv12()`.
    """
    if native.ndim != 2 or native.dtype != torch.uint8:
        raise UnsupportedFrameError("Expected two-dimensional NV12 uint8")
    h = native.shape[0] * 2 // 3
    w = native.shape[1]
    if native.stride(1) != 1 or native.shape[0] % 3 or h % 2 or w % 2:
        raise UnsupportedFrameError("Unsupported NV12 plane layout")
    ratio = min(640 / h, 640 / w)
    if ratio > 1:
        raise UnsupportedFrameError("Upscaling is outside the tested envelope")
    rh, rw = round(h * ratio), round(w * ratio)
    dh, dw = 640 - rh, 640 - rw
    if not square:
        dh, dw = dh % 32, dw % 32
    oh, ow = rh + dh, rw + dw
    top, left = round(dh / 2 - 0.1), round(dw / 2 - 0.1)
    xs, ys = _axis(w, rw), _axis(h, rh)
    output = torch.empty((1, 3, oh, ow), dtype=torch.uint8, device="cuda")
    driver, module, function = kernel()
    values = [
        ct.c_void_p(native.data_ptr()),
        ct.c_void_p(output.data_ptr()),
        ct.c_void_p(xs.data_ptr()),
        ct.c_void_p(ys.data_ptr()),
    ]
    values.extend(
        ct.c_int(value)
        for value in [native.stride(0), h, oh, ow, rh, rw, top, left, int(full_range)]
    )
    pointers = (ct.c_void_p * len(values))(
        *[ct.cast(ct.pointer(value), ct.c_void_p) for value in values]
    )
    check(
        driver.cuLaunchKernel(
            function,
            (oh * ow + 255) // 256,
            1,
            1,
            256,
            1,
            1,
            0,
            ct.c_void_p(torch.cuda.current_stream().cuda_stream),
            pointers,
            None,
        )
    )
    return output.to(dtype).div_(255)
