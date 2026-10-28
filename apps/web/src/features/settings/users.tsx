"use client";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useAuth } from "@/hooks/use-auth";
import { QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatDate } from "@/lib/utils";

export type RoleInfo = { code: string; name: string; permissions: string[] };
type User = { id: string; email: string; full_name: string; is_active: boolean; must_change_password: boolean; last_login_at: string | null; is_demo: boolean; created_at: string; role: { code: string; name: string } };

export const useRoles = () => useQuery<{ roles: RoleInfo[]; permissions: { code: string; description: string }[] }>({ queryKey: ["admin-roles"], queryFn: () => api("/admin/roles") });

function NewUser({ roles }: { roles: RoleInfo[] }) {
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email: "", full_name: "", role_code: "VIEWER", password: "" });
  const pwOk = f.password.length >= 10 && /[A-Z]/.test(f.password) && /[a-z]/.test(f.password) && /\d/.test(f.password);
  const create = useAction(() => api("/admin/users", { body: f }), {
    success: "Đã tạo người dùng (bắt buộc đổi mật khẩu lần đầu)", invalidate: [["admin-users"], ["users-dir"]],
    onSuccess: () => { setOpen(false); setF({ email: "", full_name: "", role_code: "VIEWER", password: "" }); },
  });
  return (
    <>
      <Button onClick={() => setOpen(true)} data-testid="new-user"><Plus />Thêm người dùng</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader><DialogTitle>Thêm người dùng</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <Field label="Email"><Input value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="u-email" /></Field>
            <Field label="Họ tên"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} data-testid="u-name" /></Field>
            <Field label="Vai trò">
              <NativeSelect value={f.role_code} onChange={(e) => setF({ ...f, role_code: e.target.value })} data-testid="u-role">
                {roles.map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
              </NativeSelect>
            </Field>
            <Field label="Mật khẩu khởi tạo" error={f.password && !pwOk ? "≥10 ký tự, có chữ hoa, chữ thường, chữ số" : undefined}>
              <Input type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} data-testid="u-password" />
            </Field>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>Huỷ</Button>
            <Button disabled={!pwOk || !f.email || f.full_name.length < 2} loading={create.isPending} onClick={() => create.mutate(undefined)} data-testid="u-create">Tạo</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function UsersTab() {
  const { me, has } = useAuth();
  const roles = useRoles();
  const q = useQuery<User[]>({ queryKey: ["admin-users"], queryFn: () => api("/admin/users"), enabled: has("admin.users") });
  const upd = useAction((v: { id: string; body: Record<string, unknown> }) => api(`/admin/users/${v.id}`, { method: "PATCH", body: v.body }),
    { success: "Đã cập nhật người dùng", invalidate: [["admin-users"], ["users-dir"]] });
  if (!has("admin.users")) return <p className="text-sm text-slate-500">Bạn không có quyền quản lý người dùng.</p>;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between"><CardTitle>Người dùng</CardTitle>{roles.data && <NewUser roles={roles.data.roles} />}</CardHeader>
      <CardContent>
        <QueryView q={q}>
          {(users) => (
            <Table data-testid="users-table">
              <THead><TR><TH>Email</TH><TH>Họ tên</TH><TH>Vai trò</TH><TH>Đăng nhập gần nhất</TH><TH>Hoạt động</TH></TR></THead>
              <TBody>
                {users.map((u) => (
                  <TR key={u.id} data-testid="user-row">
                    <TD>{u.email} {u.is_demo && <Badge variant="yellow">DEMO</Badge>} {u.must_change_password && <Badge variant="orange">Cần đổi MK</Badge>}</TD>
                    <TD>{u.full_name}</TD>
                    <TD>
                      <NativeSelect className="w-52" value={u.role.code} disabled={u.id === me?.id} data-testid="user-role"
                        onChange={(e) => upd.mutate({ id: u.id, body: { role_code: e.target.value } })}>
                        {(roles.data?.roles ?? []).map((r) => <option key={r.code} value={r.code}>{r.name}</option>)}
                      </NativeSelect>
                    </TD>
                    <TD className="text-xs">{formatDate(u.last_login_at)}</TD>
                    <TD><Switch checked={u.is_active} disabled={u.id === me?.id} onCheckedChange={(v) => upd.mutate({ id: u.id, body: { is_active: v } })} data-testid="user-active" aria-label="Kích hoạt" /></TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
    </Card>
  );
}

export function RolesTab() {
  const q = useRoles();
  return (
    <Card>
      <CardHeader><CardTitle>Vai trò & ma trận phân quyền</CardTitle></CardHeader>
      <CardContent>
        <QueryView q={q}>
          {(d) => (
            <Table data-testid="roles-matrix">
              <THead><TR><TH>Quyền</TH>{d.roles.map((r) => <TH key={r.code} className="text-center text-[10px]">{r.name}</TH>)}</TR></THead>
              <TBody>
                {d.permissions.map((p) => (
                  <TR key={p.code}>
                    <TD><p className="font-mono text-xs">{p.code}</p><p className="text-xs text-slate-500">{p.description}</p></TD>
                    {d.roles.map((r) => <TD key={r.code} className="text-center">{r.permissions.includes(p.code) ? <span className="text-emerald-600">✔</span> : <span className="text-slate-300">—</span>}</TD>)}
                  </TR>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
    </Card>
  );
}
