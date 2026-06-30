"use client";

import { CollectionsAssistant } from "@/components/domain/collections/CollectionsAssistant";
import { useRequireAuth } from "@/auth/useRequireAuth";

export default function CollectionsAssistantPage() {
  const ready = useRequireAuth();
  if (!ready) return null;
  return <CollectionsAssistant />;
}
