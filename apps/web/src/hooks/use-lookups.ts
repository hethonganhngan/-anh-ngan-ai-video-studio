"use client";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { ChannelMini, UserDir } from "@/types/api";

export const useChannels = () => useQuery<ChannelMini[]>({ queryKey: ["channels-mini"], queryFn: () => api("/projects/channels"), staleTime: 300_000 });
export const useUsers = () => useQuery<UserDir[]>({ queryKey: ["users-dir"], queryFn: () => api("/admin/users/directory"), staleTime: 300_000 });
