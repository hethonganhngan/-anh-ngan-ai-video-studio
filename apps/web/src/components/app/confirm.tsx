"use client";
import { useState, type ReactNode } from "react";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input, Textarea } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

/** Nút có hộp thoại xác nhận; requireText/requireReason cho thao tác quan trọng. */
export function ConfirmButton({ children, title, description, onConfirm, requireText, requireReason, confirmLabel = "Xác nhận", ...btn }: {
  children: ReactNode; title: string; description?: string; onConfirm: (reason: string) => Promise<unknown> | unknown;
  requireText?: string; requireReason?: boolean; confirmLabel?: string;
} & Omit<ButtonProps, "onClick">) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const ok = (!requireText || text === requireText) && (!requireReason || text.trim().length >= 3);
  return (
    <>
      <Button {...btn} onClick={() => { setText(""); setOpen(true); }}>{children}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description && <DialogDescription>{description}</DialogDescription>}
          </DialogHeader>
          {requireText && (
            <div className="space-y-1">
              <Label>Nhập <code className="rounded bg-slate-100 px-1">{requireText}</code> để xác nhận</Label>
              <Input value={text} onChange={(e) => setText(e.target.value)} data-testid="confirm-input" />
            </div>
          )}
          {requireReason && !requireText && (
            <div className="space-y-1">
              <Label>Lý do</Label>
              <Textarea value={text} onChange={(e) => setText(e.target.value)} data-testid="confirm-reason" />
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button>
            <Button variant={btn.variant === "destructive" ? "destructive" : "default"} disabled={!ok} loading={busy} data-testid="confirm-ok"
              onClick={async () => { setBusy(true); try { await onConfirm(text); setOpen(false); } finally { setBusy(false); } }}>
              {confirmLabel}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
