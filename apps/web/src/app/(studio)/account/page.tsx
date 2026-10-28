"use client";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/app/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/app/field";

const schema = z.object({
  current_password: z.string().min(1, "Nhập mật khẩu hiện tại"),
  new_password: z.string().min(10, "Tối thiểu 10 ký tự").regex(/[A-Z]/, "Cần chữ hoa").regex(/[a-z]/, "Cần chữ thường").regex(/\d/, "Cần chữ số"),
  confirm: z.string(),
}).refine((v) => v.new_password === v.confirm, { message: "Mật khẩu nhập lại không khớp", path: ["confirm"] });
type F = z.infer<typeof schema>;

export default function AccountPage() {
  const { me, refresh } = useAuth();
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<F>({ resolver: zodResolver(schema) });
  const onSubmit = async (v: F) => {
    try {
      await api("/auth/change-password", { body: { current_password: v.current_password, new_password: v.new_password } });
      toast.success("Đã đổi mật khẩu");
      reset();
      refresh();
    } catch (e) { toast.error(errorMessage(e)); }
  };
  return (
    <div className="max-w-xl">
      <PageHeader title="Tài khoản của tôi" description={`${me?.full_name} · ${me?.email} · ${me?.role.name}`} />
      <Card>
        <CardHeader><CardTitle>Đổi mật khẩu</CardTitle></CardHeader>
        <CardContent>
          <form className="space-y-3" onSubmit={handleSubmit(onSubmit)}>
            <Field label="Mật khẩu hiện tại" error={errors.current_password?.message}><Input type="password" {...register("current_password")} /></Field>
            <Field label="Mật khẩu mới" error={errors.new_password?.message}><Input type="password" {...register("new_password")} /></Field>
            <Field label="Nhập lại mật khẩu mới" error={errors.confirm?.message}><Input type="password" {...register("confirm")} /></Field>
            <Button type="submit" loading={isSubmitting}>Cập nhật</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
