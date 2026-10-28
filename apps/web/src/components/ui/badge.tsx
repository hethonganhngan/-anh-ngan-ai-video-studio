import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap", {
  variants: {
    variant: {
      default: "border-brand-100 bg-brand-50 text-brand-700",
      gray: "border-slate-200 bg-slate-50 text-slate-700",
      green: "border-emerald-200 bg-emerald-50 text-emerald-700",
      yellow: "border-amber-200 bg-amber-50 text-amber-800",
      orange: "border-orange-200 bg-orange-50 text-orange-700",
      red: "border-red-200 bg-red-50 text-red-700",
      purple: "border-violet-200 bg-violet-50 text-violet-700",
      navy: "border-navy-700 bg-navy-800 text-white",
    },
  },
  defaultVariants: { variant: "default" },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}
export const Badge = ({ className, variant, ...props }: BadgeProps) => (
  <span className={cn(badgeVariants({ variant }), className)} {...props} />
);
export type BadgeVariant = NonNullable<BadgeProps["variant"]>;
