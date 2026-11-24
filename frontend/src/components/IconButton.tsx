import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'

interface IconButtonProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, 'type' | 'title' | 'aria-label' | 'children'> {
  label: string
  description?: string | null
  icon: ReactNode
  ref?: Ref<HTMLButtonElement>
}

export function IconButton({ label, description, icon, className, ref, ...props }: IconButtonProps) {
  return (
    <button {...props} ref={ref} type="button" className={className ? `icon-button ${className}` : 'icon-button'} aria-label={label} aria-description={description ?? undefined} title={description ? `${label}: ${description}` : label}>
      {icon}
    </button>
  )
}

export function Icon({ children }: { children: ReactNode }) {
  return (
    <svg className="action-icon" viewBox="0 0 16 16" aria-hidden="true">
      {children}
    </svg>
  )
}
