import CloseLineIcon from "remixicon-react/CloseLineIcon"
import { cn } from "@/utils"

interface ModalProps {
  isOpen: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  icon?: React.ReactNode
  children: React.ReactNode
  className?: string
  hideClose?: boolean
}

export function Modal({ isOpen, onClose, title, subtitle, icon, children, className, hideClose }: ModalProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 transition-opacity"
        onClick={onClose}
      />

      <div className={cn(
        "relative bg-[#111111] border border-[#2A2A2A] rounded-xl shadow-2xl w-full max-w-md overflow-hidden animate-in fade-in zoom-in duration-200",
        className
      )}>

        {(title || icon) && (
          <div className="px-6 pt-6 pb-4 flex items-start justify-between">
            <div className="flex items-start gap-4">
              {icon}
              <div>
                {title && <h3 className="text-lg font-semibold text-white leading-tight">{title}</h3>}
                {subtitle && <p className="text-sm text-[#A1A1AA] mt-1 leading-relaxed">{subtitle}</p>}
              </div>
            </div>
            {!hideClose && (
              <button
                onClick={onClose}
                className="text-[#71717A] hover:text-white transition-colors"
              >
                <CloseLineIcon size={20} />
              </button>
            )}
          </div>
        )}

        {!title && !icon && !hideClose && (
          <button
            onClick={onClose}
            className="absolute right-4 top-4 text-[#71717A] hover:text-white transition-colors z-10"
          >
            <CloseLineIcon size={20} />
          </button>
        )}

        <div className="px-6 pb-6">
          {children}
        </div>
      </div>
    </div>
  )
}
