"use client";

import { CustomerServiceAssistant } from "@/components/domain/customer-service/CustomerServiceAssistant";
import { useRequireAuth } from "@/auth/useRequireAuth";

export default function CustomerServicePage() {
  const ready = useRequireAuth();
  if (!ready) return null;
  return <CustomerServiceAssistant />;
}
