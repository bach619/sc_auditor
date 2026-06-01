interface PageHeaderProps {
  title: string
  description?: string
}

export function PageHeader({ title, description }: PageHeaderProps) {
  return (
    <div className="mb-6">
      <h1 className="text-2xl font-bold dark:text-[#d4d4dc] light:text-[#09090b]">{title}</h1>
      {description && (
        <p className="mt-1 text-sm dark:text-[#68687a] light:text-[#71717a]">{description}</p>
      )}
    </div>
  )
}
