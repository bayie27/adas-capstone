"""THROWAWAY NV12 -> gray letterbox CUDA kernel for this tested input envelope.

Arithmetic follows FFmpeg 4.4 yuv_2_rgb.asm/yuv2rgb.c and OpenCV 4.13 resize.cpp.
Supports full/limited-range NV12, the BT.601 software conversion, and downscaling.
Not a general decoder replacement; every input is gated against current tensors.
"""

import ctypes as ct
import json
import subprocess
from functools import lru_cache
from pathlib import Path

import numpy as np
import torch

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


def check(status):
    if status:
        raise RuntimeError(f"CUDA/NVRTC error {status}")


@lru_cache(maxsize=1)
def kernel():
    torch.cuda.init()
    library = Path(torch.__file__).parent / "lib/nvrtc64_130_0.dll"
    rtc = ct.WinDLL(str(library))
    program = ct.c_void_p()
    check(
        rtc.nvrtcCreateProgram(
            ct.byref(program), SOURCE.encode(), b"prototype.cu", 0, None, None
        )
    )
    options = (ct.c_char_p * 1)(b"--gpu-architecture=compute_86")
    result = rtc.nvrtcCompileProgram(program, 1, options)
    if result:
        size = ct.c_size_t()
        rtc.nvrtcGetProgramLogSize(program, ct.byref(size))
        log = ct.create_string_buffer(size.value)
        rtc.nvrtcGetProgramLog(program, log)
        raise RuntimeError(log.value.decode())
    size = ct.c_size_t()
    check(rtc.nvrtcGetPTXSize(program, ct.byref(size)))
    ptx = ct.create_string_buffer(size.value)
    check(rtc.nvrtcGetPTX(program, ptx))
    check(rtc.nvrtcDestroyProgram(ct.byref(program)))
    driver = ct.WinDLL("nvcuda.dll")
    module, function = ct.c_void_p(), ct.c_void_p()
    check(driver.cuModuleLoadData(ct.byref(module), ptx))
    check(driver.cuModuleGetFunction(ct.byref(function), module, b"prep"))
    return driver, module, function


@lru_cache(maxsize=40)
def axis(source, destination):
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


def source_full_range(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=pix_fmt,color_range",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    metadata = json.loads(result.stdout)["streams"][0]
    if metadata.get("pix_fmt") not in {"yuv420p", "yuvj420p"}:
        raise RuntimeError(f"Unsupported prototype input: {metadata}")
    return metadata.get("color_range") == "pc" or metadata["pix_fmt"] == "yuvj420p"


def prepare_nv12(native, square=False, dtype=torch.float32, full_range=False):
    if native.ndim != 2 or native.dtype != torch.uint8:
        raise RuntimeError("Expected two-dimensional NV12 uint8")
    h = native.shape[0] * 2 // 3
    w = native.shape[1]
    if native.stride(1) != 1 or native.shape[0] % 3 or h % 2 or w % 2:
        raise RuntimeError("Unsupported NV12 plane layout")
    ratio = min(640 / h, 640 / w)
    if ratio > 1:
        raise RuntimeError("Upscaling is outside the tested prototype envelope")
    rh, rw = round(h * ratio), round(w * ratio)
    dh, dw = 640 - rh, 640 - rw
    if not square:
        dh, dw = dh % 32, dw % 32
    oh, ow = rh + dh, rw + dw
    top, left = round(dh / 2 - 0.1), round(dw / 2 - 0.1)
    xs, ys = axis(w, rw), axis(h, rh)
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
