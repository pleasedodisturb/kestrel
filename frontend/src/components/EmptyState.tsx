/**
 * EmptyState -- shared empty state coaching component used across Pipeline,
 * Discovery, Contacts, and Skills pages.
 *
 * Implements D-07 (shared component) and D-08 (coaching tone) from 05-CONTEXT.md.
 */
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
  icon: LucideIcon;
  heading: string;
  description: string;
  ctaLabel: string;
  ctaHref?: string;
  onCtaClick?: () => void;
  className?: string;
}

export function EmptyState({
  icon: Icon,
  heading,
  description,
  ctaLabel,
  ctaHref,
  onCtaClick,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center py-20 text-center",
        className,
      )}
      data-testid="empty-state"
    >
      <Icon
        className="h-12 w-12 text-[hsl(var(--muted-foreground))]"
        aria-hidden="true"
      />
      <h2 className="mt-4 text-2xl font-semibold text-[hsl(var(--foreground))]">
        {heading}
      </h2>
      <p className="mt-2 max-w-[400px] text-sm text-[hsl(var(--muted-foreground))]">
        {description}
      </p>
      {ctaHref ? (
        <a
          href={ctaHref}
          className="mt-6 rounded-md bg-[hsl(var(--primary))] px-4 py-2 text-sm font-semibold text-[hsl(var(--primary-foreground))] hover:opacity-90"
          data-testid="empty-state-cta"
        >
          {ctaLabel}
        </a>
      ) : (
        <button
          onClick={onCtaClick}
          className="mt-6 rounded-md bg-[hsl(var(--primary))] px-4 py-2 text-sm font-semibold text-[hsl(var(--primary-foreground))] hover:opacity-90"
          data-testid="empty-state-cta"
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
}
