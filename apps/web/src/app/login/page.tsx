"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Sparkles } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Field } from "@/components/app/field";

const schema = z.object({
  email: z.string().min(3, "Nhập email").regex(/^[^@\s]+@[^@\s]+\.[^@\s]+$/, "Email không hợp lệ"),
  password: z.string().min(1, "Nhập mật khẩu"),
});
type F = z.infer<typeof schema>;

function LoginForm() {
  const router = useRouter();
  const sp = useSearchParams();
  const qc = useQueryClient();
  const [err, setErr] = useState<string | null>(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<F>({ resolver: zodResolver(schema) });
  const onSubmit = async (v: F) => {
    setErr(null);
    try {
      await api("/auth/login", { body: v });
      await qc.invalidateQueries({ queryKey: ["me"] });
      const next = sp.get("next");
      router.replace(next && next.startsWith("/") && !next.startsWith("//") ? next : "/dashboard");
    } catch (e) {
      setErr(errorMessage(e));
    }
  };
  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
      <Field label="Email" error={errors.email?.message}>
        <Input type="email" autoComplete="username" {...register("email")} data-testid="login-email" aria-invalid={!!errors.email} />
      </Field>
      <Field label="Mật khẩu" error={errors.password?.message}>
        <Input type="password" autoComplete="current-password" {...register("password")} data-testid="login-password" aria-invalid={!!errors.password} />
      </Field>
      {err && <p className="rounded-lg bg-red-50 p-2 text-sm text-red-700" role="alert" data-testid="login-error">{err}</p>}
      <Button type="submit" className="w-full" loading={isSubmitting} data-testid="login-submit">Đăng nhập</Button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-navy-950 via-navy-900 to-brand-700 p-4">
      <Card className="w-full max-w-md">
        <CardContent className="p-8">
          <div className="mb-6 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600"><Sparkles className="h-6 w-6 text-white" /></div>
            <div>
              <h1 className="text-lg font-bold">Ánh Ngân AI Video Studio</h1>
              <p className="text-xs text-slate-500">TRAO NIỀM TIN – NHẬN GIÁ TRỊ</p>
            </div>
          </div>
          <Suspense><LoginForm /></Suspense>
          <p className="mt-6 text-center text-xs text-slate-400">Hệ thống Sữa Ánh Ngân · V2.0</p>
        </CardContent>
      </Card>
    </div>
  );
}
