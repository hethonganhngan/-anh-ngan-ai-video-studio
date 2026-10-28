"use client";
import { PageHeader } from "@/components/app/page-header";
import { RequirePermission } from "@/components/app/require";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharactersTab } from "@/features/characters/characters-tab";
import { VoicesTab } from "@/features/characters/voices-tab";
import { SceneLocksTab } from "@/features/characters/scene-locks-tab";

export default function CharactersPage() {
  return (
    <RequirePermission perm="character.view">
      <PageHeader code="M04" title="Character & Voice Studio" description="Quản lý nhân vật, ảnh tham chiếu, Character Lock / Voice Lock / Scene Lock có phiên bản bất biến, consent và quyền sử dụng." />
      <Tabs defaultValue="characters">
        <TabsList>
          <TabsTrigger value="characters" data-testid="tab-characters">Nhân vật</TabsTrigger>
          <TabsTrigger value="voices" data-testid="tab-voices">Giọng nói</TabsTrigger>
          <TabsTrigger value="scenes" data-testid="tab-scene-locks">Scene Lock</TabsTrigger>
        </TabsList>
        <TabsContent value="characters"><CharactersTab /></TabsContent>
        <TabsContent value="voices"><VoicesTab /></TabsContent>
        <TabsContent value="scenes"><SceneLocksTab /></TabsContent>
      </Tabs>
    </RequirePermission>
  );
}
