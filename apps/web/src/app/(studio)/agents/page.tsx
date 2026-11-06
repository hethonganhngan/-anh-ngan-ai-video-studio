"use client";
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Settings2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAction } from "@/hooks/use-mutate";
import { useAuth } from "@/hooks/use-auth";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission } from "@/components/app/require";
import { EmptyState, QueryView } from "@/components/app/states";
import { Field } from "@/components/app/field";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { formatDate, formatNumber, formatVND } from "@/lib/utils";
import type { Page } from "@/types/api";
import { SkillsCard } from "@/features/agents/skills";

type Agent = {
  code: string; name: string; role: string; uses_llm: boolean; provider_code: string; model: string; is_enabled: boolean;
  allowed_actions: string[]; prompt_template_code: string | null; max_runs_per_day: number; max_cost_per_run: number;
  max_tokens: number; timeout_sec: number; status: string;
  stats: { runs: number; tokens: number; cost: number; avg_latency_ms: number; errors: number; error_rate: number; last_run_at: string | null };
};
type Exec = {
  id: string; agent_code: string; action: string; model: string; provider_code: string; prompt_version_label: string | null;
  project_id: string | null; input_ref: Record<string, unknown>; output_ref: Record<string, unknown>; input_tokens: number;
  output_tokens: number; cost: string; is_simulated: boolean; latency_ms: number; status: string; error: string | null;
  triggered_by: string | null; started_at: string; finished_at: string | null;
};
const MODELS: Record<string, string[]> = { "mock-llm": ["mock-deterministic-v1"], anthropic: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"], gemini: ["gemini-3.8-flash", "gemini-4-argon", "gemini-3.5-flash-lite"] };
const EXEC_STATUS: Record<string, "green" | "red" | "purple" | "gray"> = { SUCCEEDED: "green", FAILED: "red", RUNNING: "purple", REJECTED: "gray" };

function ConfigDialog({ a, onClose }: { a: Agent; onClose: () => void }) {
  const [f, setF] = useState({ max_runs_per_day: a.max_runs_per_day, max_cost_per_run: a.max_cost_per_run, max_tokens: a.max_tokens, timeout_sec: a.timeout_sec, provider_code: a.provider_code, model: a.model });
  const save = useAction(() => {
    const body: Record<string, unknown> = { max_runs_per_day: f.max_runs_per_day, max_cost_per_run: f.max_cost_per_run, max_tokens: f.max_tokens, timeout_sec: f.timeout_sec };
    if (a.uses_llm) { body.provider_code = f.provider_code; body.model = f.model; }
    return api(`/agents/${a.code}`, { method: "PATCH", body });
  }, { success: "Đã lưu cấu hình Agent", invalidate: [["agents"]], onSuccess: onClose });
  const num = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF((x) => ({ ...x, [k]: Number(e.target.value) }));
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent>
        <DialogHeader><DialogTitle>Cấu hình {a.code} — {a.name}</DialogTitle></DialogHeader>
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Số lần chạy tối đa / ngày"><Input type="number" min={1} value={f.max_runs_per_day} onChange={num("max_runs_per_day")} data-testid="cfg-runs" /></Field>
          <Field label="Chi phí tối đa / lần (VND)"><Input type="number" min={0} value={f.max_cost_per_run} onChange={num("max_cost_per_run")} data-testid="cfg-cost" /></Field>
          <Field label="Max tokens"><Input type="number" min={256} value={f.max_tokens} onChange={num("max_tokens")} data-testid="cfg-tokens" /></Field>
          <Field label="Timeout (giây)"><Input type="number" min={5} value={f.timeout_sec} onChange={num("timeout_sec")} data-testid="cfg-timeout" /></Field>
          {a.uses_llm ? (
            <>
              <Field label="Provider">
                <NativeSelect value={f.provider_code} onChange={(e) => setF((x) => ({ ...x, provider_code: e.target.value, model: MODELS[e.target.value][0] }))} data-testid="cfg-provider">
                  {Object.keys(MODELS).map((p) => <option key={p} value={p}>{p}</option>)}
                </NativeSelect>
              </Field>
              <Field label="Model">
                <NativeSelect value={f.model} onChange={(e) => setF((x) => ({ ...x, model: e.target.value }))} data-testid="cfg-model">
                  {MODELS[f.provider_code]?.map((m) => <option key={m} value={m}>{m}</option>)}
                </NativeSelect>
              </Field>
            </>
          ) : <p className="text-sm text-slate-500 md:col-span-2">Agent rule-engine: phép tính xác định, không dùng LLM.</p>}
          <div className="md:col-span-2">
            <p className="text-sm font-medium">Phạm vi hành động (cố định theo mã nguồn, không mở rộng được)</p>
            <div className="mt-1 flex flex-wrap gap-1">{a.allowed_actions.map((x) => <Badge key={x} variant="gray">{x}</Badge>)}</div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Huỷ</Button>
          <Button onClick={() => save.mutate(undefined)} loading={save.isPending} data-testid="cfg-save">Lưu</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function Executions() {
  const [agent, setAgent] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const p = new URLSearchParams({ page_size: "100" });
  if (agent) p.set("agent_code", agent);
  if (status) p.set("status", status);
  const q = useQuery<Page<Exec>>({ queryKey: ["agent-exec", p.toString()], queryFn: () => api(`/agents/executions?${p}`) });
  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle>Lịch sử thực thi (Agent Logs)</CardTitle>
        <div className="flex gap-2">
          <NativeSelect className="w-40" value={agent} onChange={(e) => setAgent(e.target.value)} data-testid="exec-agent">
            <option value="">Mọi Agent</option>
            {Array.from({ length: 10 }, (_, i) => `A${String(i + 1).padStart(2, "0")}`).map((c) => <option key={c} value={c}>{c}</option>)}
          </NativeSelect>
          <NativeSelect className="w-40" value={status} onChange={(e) => setStatus(e.target.value)} data-testid="exec-status">
            <option value="">Mọi trạng thái</option>
            {["SUCCEEDED", "FAILED", "RUNNING"].map((s) => <option key={s} value={s}>{s}</option>)}
          </NativeSelect>
        </div>
      </CardHeader>
      <CardContent>
        <QueryView q={q} isEmpty={(d) => d.items.length === 0} empty={<EmptyState title="Chưa có lần chạy nào" />}>
          {(d) => (
            <Table data-testid="exec-table">
              <THead><TR><TH>Thời gian</TH><TH>Agent</TH><TH>Hành động</TH><TH>Model</TH><TH>Prompt</TH><TH>Token</TH><TH>Chi phí</TH><TH>Latency</TH><TH>Trạng thái</TH></TR></THead>
              <TBody>
                {d.items.map((e) => (
                  <Fragment key={e.id}>
                    <TR className="cursor-pointer" onClick={() => setOpen(open === e.id ? null : e.id)} data-testid="exec-row">
                      <TD className="text-xs">{formatDate(e.started_at)}</TD>
                      <TD className="font-mono">{e.agent_code}</TD>
                      <TD>{e.action}</TD>
                      <TD className="text-xs">{e.provider_code}/{e.model}</TD>
                      <TD className="text-xs">{e.prompt_version_label ?? "—"}</TD>
                      <TD>{formatNumber(e.input_tokens + e.output_tokens)}</TD>
                      <TD>{formatVND(e.cost)}{e.is_simulated && Number(e.cost) > 0 && <span className="ml-1 text-[10px] text-amber-700">MP</span>}</TD>
                      <TD>{e.latency_ms} ms</TD>
                      <TD><Badge variant={EXEC_STATUS[e.status] ?? "gray"}>{e.status}</Badge></TD>
                    </TR>
                    {open === e.id && (
                      <TR>
                        <TD colSpan={9} className="bg-slate-50">
                          <div className="grid gap-2 md:grid-cols-2" data-testid="exec-detail">
                            <div><p className="text-xs font-semibold">Input ref</p><pre className="overflow-auto text-xs">{JSON.stringify(e.input_ref, null, 2)}</pre></div>
                            <div><p className="text-xs font-semibold">Output ref</p><pre className="overflow-auto text-xs">{JSON.stringify(e.output_ref, null, 2)}</pre></div>
                            {e.error && <p className="text-sm text-red-700 md:col-span-2">Lỗi: {e.error}</p>}
                            <p className="text-xs text-slate-500 md:col-span-2">Kích hoạt bởi: {e.triggered_by ?? "hệ thống"} · Dự án: {e.project_id ?? "—"}</p>
                          </div>
                        </TD>
                      </TR>
                    )}
                  </Fragment>
                ))}
              </TBody>
            </Table>
          )}
        </QueryView>
      </CardContent>
    </Card>
  );
}

export default function AgentsPage() {
  const { has } = useAuth();
  const q = useQuery<Agent[]>({ queryKey: ["agents"], queryFn: () => api("/agents") });
  const [cfg, setCfg] = useState<Agent | null>(null);
  const toggle = useAction((v: { code: string; on: boolean }) => api(`/agents/${v.code}`, { method: "PATCH", body: { is_enabled: v.on } }),
    { success: "Đã cập nhật trạng thái Agent", invalidate: [["agents"]] });
  return (
    <RequirePermission perm="agent.view">
      <PageHeader code="M14" title="AI Agent Control Center" description="10 vai trò AI Agent dùng chung hạ tầng mô hình. Agent không có quyền phê duyệt hay xuất bản." />
      <QueryView q={q}>
        {(agents) => (
          <Card className="mb-4">
            <CardContent className="pt-5">
              <Table data-testid="agents-table">
                <THead><TR><TH>Agent</TH><TH>Vai trò</TH><TH>Provider / Model</TH><TH>Prompt</TH><TH>Lần chạy (30 ngày)</TH><TH>Token</TH><TH>Chi phí</TH><TH>Lỗi</TH><TH>Latency TB</TH><TH>Bật</TH><TH></TH></TR></THead>
                <TBody>
                  {agents.map((a) => (
                    <TR key={a.code} data-testid={`agent-${a.code}`}>
                      <TD><p className="font-mono text-xs text-slate-500">{a.code}</p><p className="font-medium">{a.name}</p></TD>
                      <TD className="max-w-xs text-xs text-slate-600">{a.role}</TD>
                      <TD className="text-xs">{a.provider_code}<br />{a.model}</TD>
                      <TD className="text-xs">{a.prompt_template_code ?? "—"}</TD>
                      <TD>{a.stats.runs}<p className="text-[10px] text-slate-400">{a.stats.last_run_at ? formatDate(a.stats.last_run_at) : "chưa chạy"}</p></TD>
                      <TD>{formatNumber(a.stats.tokens)}</TD>
                      <TD>{formatVND(a.stats.cost)}</TD>
                      <TD>{a.stats.errors > 0 ? <Badge variant="red">{a.stats.errors} ({a.stats.error_rate}%)</Badge> : <Badge variant="green">0</Badge>}</TD>
                      <TD>{a.stats.avg_latency_ms} ms</TD>
                      <TD><Switch checked={a.is_enabled} disabled={!has("agent.manage")} onCheckedChange={(on) => toggle.mutate({ code: a.code, on })} data-testid={`toggle-${a.code}`} aria-label={`Bật ${a.code}`} /></TD>
                      <TD>{has("agent.manage") && <Button size="sm" variant="ghost" onClick={() => setCfg(a)} data-testid={`config-${a.code}`}><Settings2 />Cấu hình</Button>}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </QueryView>
      {q.data && <SkillsCard agents={q.data.filter((a) => a.uses_llm).map((a) => ({ code: a.code, name: a.name }))} />}
      <Executions />
      {cfg && <ConfigDialog a={cfg} onClose={() => setCfg(null)} />}
    </RequirePermission>
  );
}
