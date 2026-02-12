# Bank-Grade Financial Application Architecture Guide

**Version:** 1.0  
**Last Updated:** February 2026  
**Framework:** Next.js 16 + TypeScript + React 19.2  
**Target Scale:** 10K-100K users, 100K-1M transactions/day  
**Compliance:** SOC 2 Type II, GDPR  

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Technology Stack](#technology-stack)
3. [Architectural Principles](#architectural-principles)
4. [Directory Structure](#directory-structure)
5. [Component Abstraction Patterns](#component-abstraction-patterns)
6. [State Management](#state-management)
7. [Form Handling & Validation](#form-handling--validation)
8. [Server Actions Pattern](#server-actions-pattern)
9. [Real-Time Architecture](#real-time-architecture)
10. [Security Implementation](#security-implementation)
11. [Audit Logging & Compliance](#audit-logging--compliance)
12. [Error Handling & Boundaries](#error-handling--boundaries)
13. [Configuration System](#configuration-system)
14. [Code Standards & Conventions](#code-standards--conventions)
15. [Testing Strategy](#testing-strategy)

---

## Executive Summary

This is a **backend-driven, security-first architecture** for a growth-stage fintech application. The frontend is intentionally thin—most business logic lives on the server. Client-side code focuses on:
- User experience (UI rendering, animations, real-time updates)
- Client-side validation (for UX feedback only)
- State synchronization (TanStack Query + WebSockets + SSE)
- Security enforcement (token management, DLP logging)

**Core Principles:**
- Single Responsibility Principle (SRP) enforced via directory structure
- Type-safety throughout (TypeScript strict mode)
- Accessibility-first (WCAG AAA compliance)
- Performance-optimized (Web Vitals targets: INP < 100ms, CLS < 0.1)
- Security by design (encryption, audit logs, rate limiting at backend)

---

## Technology Stack

### Core Framework
- **Next.js 16** - App Router (RSC first), Server Actions, Edge Runtime support
- **React 19.2** - React Compiler enabled for automatic optimization
- **TypeScript 5.x** - Strict mode, strict null checks
- **Node.js 20+** - LTS for production stability

### State Management
- **TanStack Query v5** - Server state (caching, synchronization, refetching)
- **Zustand v4** - Client state (UI state, sidebar, theme, preferences)
- **React Context** - Theme provider, Layout provider, Feature flags

### Styling & UI
- **Tailwind CSS 4** - Utility-first CSS with logical properties (RTL/LTR)
- **CSS Variables** - Design tokens for theming (light/dark mode, accessibility)
- **shadcn/ui** - Pre-built accessible components (Button, Input, Card, Modal, Drawer)
- **Radix UI v4** - Headless component primitives
- **Framer Motion v12** - GPU-accelerated animations (wrapped in components)

### Forms & Validation
- **React Hook Form v7** - Minimal re-renders, excellent Server Actions integration
- **Zod v4** - Runtime schema validation, TypeScript-first
- **Custom `<Form>` abstraction** - Encapsulates error handling, accessibility, loading states

### Backend Communication
- **Server Actions** - Primary method (type-safe, zero-latency, CSRF-protected)
- **Socket.io** - Real-time communication (balance updates, notifications, multi-device sync)
- **TanStack Query hooks** - Automatic invalidation on Socket events

### Authentication & Security
- **Auth.js v5** (NextAuth) - Session management, OAuth integration, MFA support
- **bcryptjs** - Password hashing (if custom auth)
- **jsonwebtoken** - JWT for access tokens (optional, Session-based recommended)
- **DOMPurify** - HTML sanitization for user-generated content
- **Sentry** - Error tracking (PII-filtered)

### Database & ORM
- **PostgreSQL** - Primary database (ACID compliance, financial data integrity)
- **Prisma v5** - Type-safe ORM with auto-generated types
- **Redis** (Upstash) - Caching, session storage, pub/sub for real-time

### Developer Tooling
- **ESLint** - Custom rules for SRP, no barrel imports, no direct parent imports
- **Prettier** - Code formatting
- **Husky** - Pre-commit hooks (type-check, lint)
- **Vitest** - Unit testing (faster than Jest)
- **React Testing Library** - Component testing (accessibility-focused)
- **Storybook v7** - Component documentation and isolated testing

### Monitoring & Observability
- **Vercel Analytics** - Web Vitals monitoring
- **Sentry** - Error tracking and performance monitoring
- **Custom Audit Logger** - Application-level event logging
- **LogRocket** (optional) - Session replay for debugging

---

## Architectural Principles

### 1. Backend-Driven Architecture
- **Server is the source of truth** for all business logic
- Client validates only for UX feedback (instant feedback)
- Server validates as the final arbiter (cannot be bypassed)
- Sensitive data (PINs, OTPs, secrets) never touch client

```
User Input → Client Validation (Zod) → Server Action
             ↓
        Immediate UX Feedback (Optimistic Update)
             ↓
        Server Validation + Business Logic
             ↓
        Database Transaction
             ↓
        WebSocket Broadcast to All Devices
             ↓
        TanStack Query Invalidation + UI Update
```

### 2. Single Responsibility Principle (SRP)
- Each file/module has ONE reason to change
- Components handle only rendering logic
- Hooks handle state logic
- Services handle API communication
- Enforced via ESLint rules + directory structure

**Violation Example:**
```typescript
// ❌ WRONG: Component doing multiple things
function TransferForm() {
  const [amount, setAmount] = useState('');
  const makeRequest = async () => {
    const response = await fetch('/api/transfer', { body: { amount } });
    // Parsing, validation, error handling all mixed
  };
  return <form onSubmit={makeRequest}>...</form>;
}
```

**Compliant Example:**
```typescript
// ✅ CORRECT: Clear separation
// useTransfer hook (state + API logic)
function useTransfer() {
  return useMutation({
    mutationFn: (data: TransferInput) => transferService.execute(data),
  });
}

// Component (rendering only)
function TransferForm() {
  const { mutate, isPending } = useTransfer();
  const form = useForm<TransferInput>({ resolver: zodResolver(TransferSchema) });
  return <form onSubmit={form.handleSubmit(mutate)}>...</form>;
}
```

### 3. Type Safety
- TypeScript strict mode always
- No `any` type except in test mocks
- Leverage Zod for runtime type validation
- Prisma auto-generates types from schema

### 4. Security by Design
- Never trust client input (validate on server)
- Encrypt sensitive data at rest
- TLS 1.3 for all traffic
- HTTP-only cookies for tokens
- CSRF protection via Server Actions
- Rate limiting at backend (not frontend)
- Audit logging for all sensitive operations

### 5. Accessibility-First
- WCAG AAA compliance (AA minimum, AAA where practical)
- Semantic HTML (`<main>`, `<nav>`, `<button>` vs divs)
- ARIA labels and descriptions
- Keyboard navigation (Tab, Enter, Escape)
- Color contrast minimum 7:1 for text
- Support `prefers-reduced-motion` for animations
- Focus management for modals/drawers

### 6. Performance-Optimized
- Server-side rendering (RSC) by default
- Code splitting for features
- Image optimization (Next.js Image component)
- Web Vitals targets:
  - LCP (Largest Contentful Paint): < 2.5s
  - INP (Interaction to Next Paint): < 100ms
  - CLS (Cumulative Layout Shift): < 0.1
- Bundle size targets:
  - Initial JS: < 150KB gzipped
  - React + TanStack Query: ~80KB
  - Total with features: < 200KB

---

## Directory Structure

```
src/
├── app/                           # Next.js App Router
│   ├── layout.tsx                 # Root layout with providers
│   ├── globals.css                # Global styles + design tokens
│   ├── page.tsx                   # Homepage
│   ├── (auth)/                    # Auth route group (no sidebar layout)
│   │   ├── login/page.tsx
│   │   ├── signup/page.tsx
│   │   ├── forgot-password/page.tsx
│   │   └── layout.tsx             # Auth layout (minimal)
│   ├── (protected)/               # Protected route group (with sidebar)
│   │   ├── layout.tsx             # Protected layout with sidebar
│   │   ├── dashboard/page.tsx
│   │   ├── accounts/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   ├── transfers/
│   │   │   ├── page.tsx
│   │   │   └── [id]/page.tsx
│   │   └── settings/
│   │       ├── page.tsx
│   │       └── security/page.tsx
│   ├── api/                       # API routes (minimal, only for webhooks/third-party)
│   │   ├── webhooks/stripe/route.ts
│   │   └── health/route.ts
│   └── actions/                   # Server Actions (preferred for internal communication)
│       ├── auth.actions.ts
│       ├── transfers.actions.ts
│       ├── accounts.actions.ts
│       └── settings.actions.ts
│
├── components/                    # UI components (layer 1: atomic)
│   ├── ui/                        # Base UI components from shadcn
│   │   ├── button.tsx
│   │   ├── input.tsx
│   │   ├── form.tsx
│   │   ├── modal.tsx
│   │   ├── drawer.tsx
│   │   ├── card.tsx
│   │   └── [other shadcn components]
│   ├── abstraction/               # Custom abstraction layer (layer 2)
│   │   ├── Form.tsx               # Form wrapper (accessibility + error handling)
│   │   ├── Button.tsx             # Button variant with loading state
│   │   ├── Input.tsx              # Input with validation feedback
│   │   ├── Field.tsx              # Field wrapper (label + error + hint)
│   │   ├── Modal.tsx              # Modal with focus management
│   │   ├── Drawer.tsx             # Drawer with slide animation
│   │   ├── Animate.tsx            # Framer Motion wrapper
│   │   ├── FeatureGuard.tsx        # Error boundary + audit logging wrapper
│   │   ├── ErrorBoundary.tsx
│   │   └── Skeleton.tsx           # Loading placeholder
│   └── domain/                    # Domain-specific components (layer 3)
│       ├── account/               # Reusable account components
│       │   ├── AccountCard.tsx
│       │   ├── AccountBalance.tsx
│       │   └── AccountSelector.tsx
│       ├── transfer/              # Reusable transfer components
│       │   ├── TransferForm.tsx
│       │   ├── TransferHistory.tsx
│       │   └── TransferConfirmation.tsx
│       └── auth/                  # Reusable auth components
│           ├── LoginForm.tsx
│           ├── SignupForm.tsx
│           └── OTPInput.tsx
│
├── features/                      # Feature modules (layer 4: complete features)
│   ├── transfers/
│   │   ├── components/            # Feature-specific components
│   │   │   ├── TransferFlow.tsx
│   │   │   ├── TransfersList.tsx
│   │   │   └── TransferDetails.tsx
│   │   ├── hooks/                 # Feature hooks
│   │   │   ├── useTransfer.ts
│   │   │   └── useTransferHistory.ts
│   │   ├── services/              # API communication
│   │   │   └── transfer.service.ts
│   │   ├── types/                 # TS types
│   │   │   └── transfer.types.ts
│   │   ├── schemas/               # Zod schemas
│   │   │   └── transfer.schema.ts
│   │   ├── queries/               # TanStack Query keys
│   │   │   └── transfer.queries.ts
│   │   └── README.md              # Feature documentation
│   │
│   ├── accounts/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── types/
│   │   ├── schemas/
│   │   ├── queries/
│   │   └── README.md
│   │
│   └── auth/
│       ├── components/
│       ├── hooks/
│       ├── services/
│       ├── types/
│       ├── schemas/
│       ├── queries/
│       └── README.md
│
├── hooks/                         # Shared hooks
│   ├── useAuth.ts                 # Authentication state
│   ├── useAuditLog.ts             # Audit logging
│   ├── useFeatureFlag.ts          # Feature flags
│   ├── useLocalStorage.ts         # LocalStorage (minimal use)
│   ├── useIdle.ts                 # Idle timer (auto-logout)
│   └── use-mobile.ts              # Responsive design
│
├── lib/                           # Utilities & helpers
│   ├── utils.ts                   # General utilities (cn, formatters, etc.)
│   ├── api-client.ts              # Axios/fetch wrapper (if needed)
│   ├── validators.ts              # Custom validation functions
│   ├── crypto.ts                  # Client-side encryption (if needed)
│   └── logger.ts                  # Client logger (PII-filtered)
│
├── services/                      # Backend-facing services (shared across features)
│   ├── api/                       # API communication layer
│   │   ├── auth.service.ts
│   │   ├── accounts.service.ts
│   │   ├── transfers.service.ts
│   │   └── api.ts                 # Axios/fetch base config
│   ├── socket/                    # WebSocket service
│   │   ├── socket.ts
│   │   ├── handlers.ts            # Event handlers
│   │   └── emitters.ts            # Event emitters
│   └── audit/                     # Audit logging service
│       └── audit.ts
│
├── store/                         # Zustand stores (client-only state)
│   ├── sidebar.store.ts           # Sidebar open/close
│   ├── theme.store.ts             # Dark/light mode
│   ├── ui.store.ts                # Modal visibility, filters, etc.
│   └── user-preferences.store.ts  # User preferences (not synced with server)
│
├── config/                        # Application configuration
│   ├── app.config.ts              # Feature flags, regions, constants
│   ├── navigation.config.ts       # Navigation structure
│   ├── feature-flags.ts           # Feature gates
│   ├── api.config.ts              # API base URLs, timeout, retry logic
│   └── constants.ts               # Global constants
│
├── types/                         # Global TypeScript types
│   ├── index.ts                   # Re-exports all types
│   ├── api.types.ts               # API request/response types
│   ├── auth.types.ts              # Authentication types
│   ├── common.types.ts            # Common domain types
│   └── ui.types.ts                # UI component props types
│
├── providers/                     # React Context providers
│   ├── AuthProvider.tsx
│   ├── ThemeProvider.tsx
│   ├── LayoutProvider.tsx
│   ├── TanStackQueryProvider.tsx
│   └── SocketProvider.tsx
│
├── middleware.ts                  # Next.js middleware (request logging, auth)
│
└── env.ts                         # Environment variable validation (Zod)
```

---

## Component Abstraction Patterns

### Pattern 1: UI Layer (shadcn components)
Raw Radix UI + Tailwind CSS components. Used internally but rarely imported directly in features.

```typescript
// components/ui/button.tsx
import { forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 rounded-md font-medium transition-colors',
  {
    variants: {
      variant: {
        primary: 'bg-blue-600 text-white hover:bg-blue-700 active:bg-blue-800',
        secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
        ghost: 'hover:bg-gray-100 text-gray-700',
      },
      size: {
        sm: 'px-3 py-1.5 text-sm',
        md: 'px-4 py-2 text-base',
        lg: 'px-6 py-3 text-lg',
      },
    },
    defaultVariants: { variant: 'primary', size: 'md' },
  }
);

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, isLoading, disabled, children, ...props }, ref) => (
    <button
      ref={ref}
      className={buttonVariants({ variant, size, className })}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <span className="animate-spin">⟳</span>}
      {children}
    </button>
  )
);
Button.displayName = 'Button';
```

### Pattern 2: Abstraction Layer (Custom wrappers)
Enhanced UI components with accessibility, error handling, and common patterns baked in.

```typescript
// components/abstraction/Form.tsx
import { ReactNode } from 'react';
import { UseFormHandleSubmit, FieldValues, Path } from 'react-hook-form';

interface FormProps<T extends FieldValues> {
  onSubmit: (data: T) => Promise<void>;
  handleSubmit: UseFormHandleSubmit<T>;
  children: ReactNode;
  isLoading?: boolean;
  className?: string;
}

export function Form<T extends FieldValues>({
  onSubmit,
  handleSubmit,
  children,
  isLoading = false,
  className,
}: FormProps<T>) {
  return (
    <form onSubmit={handleSubmit(onSubmit)} className={className} noValidate>
      {children}
    </form>
  );
}

// components/abstraction/Field.tsx
import { ReactNode } from 'react';
import { useFormContext, Controller, RegisterOptions } from 'react-hook-form';
import { FieldError } from 'react-hook-form';

interface FieldProps {
  name: string;
  label: string;
  description?: string;
  children: ReactNode;
  error?: FieldError;
  required?: boolean;
}

export function Field({ name, label, description, children, error, required }: FieldProps) {
  const id = `field-${name}`;
  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="font-medium text-sm">
        {label}
        {required && <span className="text-red-600 ml-1">*</span>}
      </label>
      <div id={`${id}-description`} className="text-xs text-gray-600">
        {description}
      </div>
      <div className="relative">
        {children}
      </div>
      {error && (
        <p className="text-sm text-red-600" role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}

// components/abstraction/Input.tsx
import { forwardRef } from 'react';
import { FieldValues, Path, UseFormRegisterReturn } from 'react-hook-form';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  registration?: UseFormRegisterReturn;
  isInvalid?: boolean;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, isInvalid, registration, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'px-3 py-2 border rounded-md transition-colors',
        isInvalid ? 'border-red-500 bg-red-50' : 'border-gray-300 focus:border-blue-500',
        className
      )}
      {...registration}
      {...props}
    />
  )
);
Input.displayName = 'Input';

// Usage in feature component
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

export function TransferForm() {
  const { control, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(TransferSchema),
  });

  return (
    <Form handleSubmit={handleSubmit} onSubmit={async (data) => {
      // Server Action call
    }}>
      <Field name="amount" label="Amount" error={errors.amount}>
        <Input type="number" placeholder="0.00" {...register('amount')} />
      </Field>
    </Form>
  );
}
```

### Pattern 3: FeatureGuard Wrapper
Wraps features with error boundary and audit logging.

```typescript
// components/abstraction/FeatureGuard.tsx
import { ReactNode, Suspense } from 'react';
import { ErrorBoundary } from './ErrorBoundary';
import { useAuditLog } from '@/hooks/useAuditLog';

interface FeatureGuardProps {
  featureName: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function FeatureGuard({ featureName, fallback, children }: FeatureGuardProps) {
  const auditLog = useAuditLog();

  return (
    <ErrorBoundary
      fallback={fallback || <FeatureError name={featureName} />}
      onError={(error) => {
        auditLog('FEATURE_ERROR', {
          feature: featureName,
          error: error.message,
          severity: 'high',
        });
      }}
    >
      <Suspense fallback={<FeatureSkeleton />}>
        {children}
      </Suspense>
    </ErrorBoundary>
  );
}

// Usage
<FeatureGuard featureName="Transfers" fallback={<TransfersError />}>
  <TransfersFlow />
</FeatureGuard>
```

---

## State Management

### Pattern 1: TanStack Query for Server State

**Query Keys Factory** (`features/transfers/queries/transfer.queries.ts`)
```typescript
export const transferQueries = {
  all: () => ['transfers'] as const,
  lists: () => [...transferQueries.all(), 'list'] as const,
  list: (filters?: TransferFilters) => [...transferQueries.lists(), { filters }] as const,
  details: () => [...transferQueries.all(), 'detail'] as const,
  detail: (id: string) => [...transferQueries.details(), id] as const,
};
```

**Hook with Query**
```typescript
// features/transfers/hooks/useTransferHistory.ts
import { useQuery } from '@tanstack/react-query';
import { transferService } from '../services/transfer.service';
import { transferQueries } from '../queries/transfer.queries';

export function useTransferHistory(filters?: TransferFilters) {
  return useQuery({
    queryKey: transferQueries.list(filters),
    queryFn: () => transferService.getHistory(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
    gcTime: 1000 * 60 * 10, // 10 minutes
  });
}
```

**Hook with Mutation** (for Server Actions)
```typescript
// features/transfers/hooks/useTransfer.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { transferAction } from '@/app/actions/transfers.actions';
import { transferQueries } from '../queries/transfer.queries';
import { useAuditLog } from '@/hooks/useAuditLog';

export function useTransfer() {
  const queryClient = useQueryClient();
  const auditLog = useAuditLog();

  return useMutation({
    mutationFn: async (data: TransferInput) => {
      auditLog('TRANSFER_INITIATED', { amount: data.amount, recipient: data.recipientId });
      return transferAction(data);
    },
    onSuccess: (data) => {
      // Optimistic update already applied, now update with real data
      queryClient.setQueryData(
        transferQueries.detail(data.id),
        data
      );
      // Invalidate lists so they refetch
      queryClient.invalidateQueries({ queryKey: transferQueries.lists() });
      
      auditLog('TRANSFER_COMPLETED', { transferId: data.id });
    },
    onError: (error) => {
      auditLog('TRANSFER_FAILED', { error: error.message });
    },
  });
}
```

**Server Action Integration**
```typescript
// features/transfers/services/transfer.service.ts
export const transferService = {
  async execute(data: TransferInput): Promise<Transfer> {
    // Call Server Action
    const result = await executeTransferAction(data);
    if (result.error) throw new Error(result.error);
    return result.data;
  },
};

// Component usage
function TransferForm() {
  const { mutate, isPending } = useTransfer();
  const form = useForm({ resolver: zodResolver(TransferSchema) });

  return (
    <Form handleSubmit={form.handleSubmit} onSubmit={(data) => mutate(data)}>
      {/* Form fields */}
    </Form>
  );
}
```

### Pattern 2: Zustand for Client UI State

```typescript
// store/sidebar.store.ts
import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface SidebarState {
  isOpen: boolean;
  toggle: () => void;
  close: () => void;
  open: () => void;
}

export const useSidebarStore = create<SidebarState>()(
  persist(
    (set) => ({
      isOpen: true,
      toggle: () => set((state) => ({ isOpen: !state.isOpen })),
      close: () => set({ isOpen: false }),
      open: () => set({ isOpen: true }),
    }),
    {
      name: 'sidebar-storage',
      partialize: (state) => ({ isOpen: state.isOpen }),
    }
  )
);

// store/theme.store.ts
import { create } from 'zustand';

interface ThemeState {
  theme: 'light' | 'dark' | 'system';
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: 'system',
  setTheme: (theme) => {
    set({ theme });
    // Apply theme to DOM
    const html = document.documentElement;
    if (theme === 'system') {
      html.classList.remove('dark', 'light');
      html.classList.add(window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    } else {
      html.classList.remove('dark', 'light');
      html.classList.add(theme);
    }
  },
}));
```

**Usage in Components**
```typescript
function Sidebar() {
  const { isOpen, toggle, close } = useSidebarStore();
  
  return (
    <>
      <button onClick={toggle}>Toggle Sidebar</button>
      {isOpen && <nav>Navigation items</nav>}
    </>
  );
}
```

---

## Form Handling & Validation

### Pattern 1: Zod Schema Definition

```typescript
// features/transfers/schemas/transfer.schema.ts
import { z } from 'zod';

export const TransferSchema = z.object({
  recipientId: z.string().uuid('Invalid recipient'),
  amount: z.number()
    .positive('Amount must be positive')
    .max(100000, 'Amount exceeds limit'),
  description: z.string().max(500).optional(),
  otp: z.string().length(6, 'OTP must be 6 digits'),
});

export type TransferInput = z.infer<typeof TransferSchema>;
```

### Pattern 2: React Hook Form + Zod Integration

```typescript
// features/transfers/components/TransferForm.tsx
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Form, Field, Input, Button } from '@/components/abstraction';
import { useTransfer } from '../hooks/useTransfer';
import { TransferSchema } from '../schemas/transfer.schema';

export function TransferForm() {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: zodResolver(TransferSchema),
    mode: 'onBlur', // Validate on blur for UX
  });

  const { mutate, isPending } = useTransfer();

  const onSubmit = async (data: TransferInput) => {
    mutate(data, {
      onSuccess: () => {
        // Show success notification
      },
      onError: (error) => {
        // Show error notification
      },
    });
  };

  return (
    <Form handleSubmit={handleSubmit} onSubmit={onSubmit}>
      <Field
        name="recipientId"
        label="Recipient"
        error={errors.recipientId}
        required
      >
        <select {...register('recipientId')}>
          <option value="">Select recipient</option>
        </select>
      </Field>

      <Field
        name="amount"
        label="Amount (USD)"
        description="Maximum $100,000 per transaction"
        error={errors.amount}
        required
      >
        <Input
          type="number"
          step="0.01"
          placeholder="0.00"
          {...register('amount', { valueAsNumber: true })}
        />
      </Field>

      <Field
        name="description"
        label="Description"
        error={errors.description}
      >
        <input
          type="text"
          placeholder="Payment for..."
          {...register('description')}
        />
      </Field>

      <Field
        name="otp"
        label="One-Time Password"
        error={errors.otp}
        required
      >
        <OTPInput {...register('otp')} />
      </Field>

      <Button type="submit" disabled={isSubmitting || isPending}>
        {isPending ? 'Processing...' : 'Confirm Transfer'}
      </Button>
    </Form>
  );
}
```

### Pattern 3: Server-Side Validation (Server Action)

```typescript
// app/actions/transfers.actions.ts
'use server';

import { auth } from '@/auth';
import { TransferSchema } from '@/features/transfers/schemas/transfer.schema';
import { transferService } from '@/features/transfers/services/transfer.service';
import { auditLog } from '@/services/audit/audit';

export async function executeTransferAction(input: unknown) {
  try {
    // 1. Authentication
    const session = await auth();
    if (!session?.user?.id) {
      throw new Error('Unauthorized');
    }

    // 2. Client validation (re-validate, client can be spoofed)
    const validatedData = TransferSchema.parse(input);

    // 3. Business logic validation (server-side authority)
    const sender = await db.user.findUnique({
      where: { id: session.user.id },
      include: { accounts: true },
    });

    if (!sender) throw new Error('User not found');

    const recipient = await db.user.findUnique({
      where: { id: validatedData.recipientId },
    });

    if (!recipient) throw new Error('Recipient not found');

    const account = sender.accounts[0];
    if (account.balance < validatedData.amount) {
      throw new Error('Insufficient funds');
    }

    // 4. Verify OTP (server-side, critical security)
    const isValidOTP = await verifyOTP(session.user.id, validatedData.otp);
    if (!isValidOTP) {
      await auditLog(session.user.id, 'TRANSFER_INVALID_OTP', {
        recipient: validatedData.recipientId,
      });
      throw new Error('Invalid OTP');
    }

    // 5. Execute transaction (within DB transaction)
    const transfer = await db.$transaction(async (tx) => {
      // Debit sender
      await tx.account.update({
        where: { id: account.id },
        data: { balance: { decrement: validatedData.amount } },
      });

      // Credit recipient
      const recipientAccount = await tx.account.findFirst({
        where: { userId: validatedData.recipientId },
      });
      await tx.account.update({
        where: { id: recipientAccount.id },
        data: { balance: { increment: validatedData.amount } },
      });

      // Create transfer record
      return tx.transfer.create({
        data: {
          senderId: session.user.id,
          recipientId: validatedData.recipientId,
          amount: validatedData.amount,
          description: validatedData.description,
          status: 'COMPLETED',
        },
      });
    });

    // 6. Audit logging
    await auditLog(session.user.id, 'TRANSFER_COMPLETED', {
      transferId: transfer.id,
      amount: transfer.amount,
      recipient: transfer.recipientId,
    });

    // 7. Emit real-time event (WebSocket broadcast)
    await socketService.broadcastToUser(session.user.id, 'TRANSFER_UPDATED', {
      transfer,
      newBalance: account.balance - validatedData.amount,
    });

    return { data: transfer, error: null };
  } catch (error) {
    // Log error securely (no sensitive data in logs)
    await auditLog(session?.user?.id || 'unknown', 'TRANSFER_FAILED', {
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    return { data: null, error: error instanceof Error ? error.message : 'Transfer failed' };
  }
}
```

---

## Server Actions Pattern

### Principles
- Type-safe (TypeScript validates input and output)
- CSRF-protected (Next.js built-in)
- Zero-latency (runs on same server as database)
- Audit-logged (every call traced)
- Error-handled (never expose internal errors to client)

### Directory Organization

```
app/actions/
├── auth.actions.ts        # Login, signup, logout, MFA
├── accounts.actions.ts    # Account management, CRUD
├── transfers.actions.ts   # Transfer operations
├── settings.actions.ts    # User settings, preferences
└── admin.actions.ts       # Admin operations (if applicable)
```

### Template for Server Action

```typescript
// app/actions/template.actions.ts
'use server';

import { auth } from '@/auth';
import { db } from '@/db';
import { MySchema } from '@/features/myfeature/schemas/my.schema';
import { auditLog } from '@/services/audit/audit';
import { socketService } from '@/services/socket/socket';

interface ActionResponse<T> {
  data: T | null;
  error: string | null;
}

/**
 * [ACTION_NAME]
 * Description of what this action does
 *
 * Security considerations:
 * - Verifies user authentication
 * - Validates input schema
 * - Checks authorization
 * - Logs audit trail
 */
export async function myAction(input: unknown): Promise<ActionResponse<MyType>> {
  try {
    // 1. Authentication
    const session = await auth();
    if (!session?.user?.id) {
      return { data: null, error: 'Unauthorized' };
    }

    // 2. Input Validation
    const validatedInput = MySchema.parse(input);

    // 3. Authorization Check
    const user = await db.user.findUnique({
      where: { id: session.user.id },
    });
    if (!user) {
      return { data: null, error: 'User not found' };
    }

    // 4. Business Logic
    const result = await db.myTable.create({
      data: {
        userId: session.user.id,
        ...validatedInput,
      },
    });

    // 5. Audit Logging
    await auditLog(session.user.id, 'MY_ACTION_COMPLETED', {
      resultId: result.id,
      timestamp: new Date(),
    });

    // 6. Real-time Broadcast (if needed)
    await socketService.broadcastToUser(session.user.id, 'MY_ACTION_UPDATED', {
      result,
    });

    return { data: result, error: null };
  } catch (error) {
    // Never expose internal errors to client
    const errorMessage = error instanceof Error ? error.message : 'An error occurred';

    // Audit the failure
    await auditLog(session?.user?.id || 'unknown', 'MY_ACTION_FAILED', {
      error: errorMessage,
    });

    // Return safe error message
    return {
      data: null,
      error: 'Operation failed. Please try again.',
    };
  }
}
```

---

## Real-Time Architecture

### WebSocket Setup with Socket.io

```typescript
// services/socket/socket.ts
import { io, Socket } from 'socket.io-client';

export class SocketService {
  private socket: Socket | null = null;

  connect(userId: string, token: string) {
    this.socket = io(process.env.NEXT_PUBLIC_WS_URL || 'http://localhost:3000', {
      query: { userId, token },
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.socket.on('connect', () => {
      console.log('[Socket] Connected');
    });

    this.socket.on('disconnect', () => {
      console.log('[Socket] Disconnected');
    });

    this.setupEventHandlers();
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    // Balance update event
    this.socket.on('BALANCE_UPDATED', (data: { newBalance: number; accountId: string }) => {
      // Invalidate query to refetch fresh data
      queryClient.invalidateQueries({
        queryKey: ['account', data.accountId],
      });
    });

    // Transfer notification
    this.socket.on('TRANSFER_NOTIFICATION', (data: { message: string; type: 'sent' | 'received' }) => {
      // Show notification
      showToast(data.message, { type: data.type });
    });

    // Session invalidation (security)
    this.socket.on('SESSION_INVALIDATED', () => {
      // Force logout and redirect to login
      logout();
    });
  }

  broadcastToUser(userId: string, event: string, data: any) {
    this.socket?.emit('broadcast', {
      userId,
      event,
      data,
      timestamp: Date.now(),
    });
  }

  disconnect() {
    this.socket?.disconnect();
  }
}

export const socketService = new SocketService();
```

### TanStack Query + Socket Integration

```typescript
// providers/SocketProvider.tsx
'use client';

import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/hooks/useAuth';
import { socketService } from '@/services/socket/socket';

export function SocketProvider({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!user) return;

    // Connect socket when user is authenticated
    socketService.connect(user.id, localStorage.getItem('token')!);

    // Setup event listeners for query invalidation
    const handleBalanceUpdate = (data: { newBalance: number; accountId: string }) => {
      queryClient.setQueryData(['account', data.accountId], (old: any) => ({
        ...old,
        balance: data.newBalance,
      }));
    };

    socketService.socket?.on('BALANCE_UPDATED', handleBalanceUpdate);

    return () => {
      socketService.socket?.off('BALANCE_UPDATED', handleBalanceUpdate);
      socketService.disconnect();
    };
  }, [user?.id, queryClient]);

  return <>{children}</>;
}
```

---

## Security Implementation

### 1. Authentication & Session Management

```typescript
// lib/auth/config.ts
import type { NextAuthConfig } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { LoginSchema } from '@/features/auth/schemas/login.schema';
import { verifyPassword } from '@/lib/crypto';

export const authConfig: NextAuthConfig = {
  providers: [
    CredentialsProvider({
      async authorize(credentials) {
        // Validate input
        const parsed = LoginSchema.safeParse(credentials);
        if (!parsed.success) return null;

        // Find user
        const user = await db.user.findUnique({
          where: { email: parsed.data.email },
        });
        if (!user) return null;

        // Verify password (bcrypt)
        const isValidPassword = await verifyPassword(parsed.data.password, user.passwordHash);
        if (!isValidPassword) {
          // Log failed attempt
          await auditLog('unknown', 'LOGIN_FAILED_INVALID_PASSWORD', {
            email: parsed.data.email,
          });
          return null;
        }

        // Check MFA requirement
        if (user.mfaEnabled) {
          return {
            id: user.id,
            email: user.email,
            requiresMFA: true,
          };
        }

        return {
          id: user.id,
          email: user.email,
          name: user.fullName,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.sub = user.id;
        token.email = user.email;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.id = token.sub!;
        session.user.email = token.email!;
      }
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/login?error=InvalidCredentials',
  },
  session: {
    strategy: 'jwt',
    maxAge: 24 * 60 * 60, // 24 hours
  },
};
```

### 2. Token Management

```typescript
// lib/crypto/token.ts
import jwt from 'jsonwebtoken';

export function generateAccessToken(userId: string, expiresIn = '15m') {
  return jwt.sign({ sub: userId }, process.env.JWT_SECRET!, {
    expiresIn,
    algorithm: 'HS256',
  });
}

export function generateRefreshToken(userId: string) {
  return jwt.sign({ sub: userId }, process.env.REFRESH_TOKEN_SECRET!, {
    expiresIn: '7d',
    algorithm: 'HS256',
  });
}

export function verifyToken(token: string, secret = process.env.JWT_SECRET!) {
  try {
    return jwt.verify(token, secret) as { sub: string; iat: number; exp: number };
  } catch (error) {
    return null;
  }
}
```

### 3. Input Sanitization

```typescript
// lib/validators/sanitize.ts
import DOMPurify from 'dompurify';

export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty);
}

export function sanitizeText(text: string): string {
  return text.trim().replace(/[<>]/g, '');
}
```

### 4. Rate Limiting (Backend)

```typescript
// middleware/rateLimit.ts
import { Ratelimit } from '@upstash/ratelimit';
import { Redis } from '@upstash/redis';

const ratelimit = new Ratelimit({
  redis: Redis.fromEnv(),
  limiter: Ratelimit.slidingWindow(10, '1 h'),
});

export async function checkRateLimit(identifier: string) {
  const { success } = await ratelimit.limit(identifier);
  return success;
}
```

---

## Audit Logging & Compliance

### Audit Logger Hook

```typescript
// hooks/useAuditLog.ts
import { useCallback } from 'react';
import { useAuth } from './useAuth';

export type AuditEventType =
  | 'LOGIN'
  | 'LOGOUT'
  | 'TRANSFER_INITIATED'
  | 'TRANSFER_COMPLETED'
  | 'TRANSFER_FAILED'
  | 'ACCOUNT_ACCESSED'
  | 'SETTINGS_CHANGED'
  | 'FAILED_LOGIN_ATTEMPT'
  | 'INVALID_OTP'
  | 'FEATURE_ERROR'
  | 'DLP_VIOLATION';

interface AuditLogData {
  [key: string]: any;
  timestamp?: number;
  severity?: 'low' | 'medium' | 'high' | 'critical';
}

export function useAuditLog() {
  const { user } = useAuth();

  return useCallback(async (event: AuditEventType, data: AuditLogData = {}) => {
    try {
      await fetch('/api/audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event,
          userId: user?.id || 'anonymous',
          data: {
            ...data,
            timestamp: data.timestamp || Date.now(),
            userAgent: navigator.userAgent,
            ip: 'server-will-determine', // IP determined server-side
          },
        }),
      });
    } catch (error) {
      // Silently fail, don't disrupt user experience
      console.error('[Audit] Failed to log event:', error);
    }
  }, [user?.id]);
}
```

### Server-Side Audit Log

```typescript
// services/audit/audit.ts
import { db } from '@/db';

export async function auditLog(
  userId: string,
  event: string,
  data: Record<string, any>,
  context?: {
    ip?: string;
    userAgent?: string;
    requestId?: string;
  }
) {
  try {
    await db.auditLog.create({
      data: {
        userId,
        event,
        data: data as any, // Store as JSON
        ipAddress: context?.ip || 'unknown',
        userAgent: context?.userAgent || 'unknown',
        requestId: context?.requestId,
        timestamp: new Date(),
      },
    });
  } catch (error) {
    // Log to error tracking (Sentry)
    console.error('[Audit] Failed to create audit log:', error);
  }
}
```

---

## Error Handling & Boundaries

### Error Boundary Component

```typescript
// components/abstraction/ErrorBoundary.tsx
'use client';

import { ReactNode } from 'react';
import { Component, ReactNode as ReactNodeType, ReactElement } from 'react';

interface Props {
  children: ReactNodeType;
  fallback?: ReactElement;
  onError?: (error: Error) => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // Log to error tracking
    console.error('[ErrorBoundary]', error, errorInfo);
    this.props.onError?.(error);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <div>Something went wrong. Please refresh the page.</div>;
    }

    return this.props.children;
  }
}
```

### Usage with FeatureGuard

```typescript
function PageWithErrorHandling() {
  return (
    <FeatureGuard featureName="Transfers" fallback={<TransferError />}>
      <TransfersFlow />
    </FeatureGuard>
  );
}
```

---

## Configuration System

### App Configuration

```typescript
// config/app.config.ts
export const appConfig = {
  // Feature flags
  features: {
    enableBiometric: process.env.NEXT_PUBLIC_ENABLE_BIOMETRIC === 'true',
    enableCrypto: process.env.NEXT_PUBLIC_ENABLE_CRYPTO === 'true',
    enableBetaUI: process.env.NEXT_PUBLIC_BETA_UI === 'true',
  },

  // Regional settings
  region: (process.env.NEXT_PUBLIC_REGION || 'US') as 'US' | 'EU' | 'APAC',
  timezone: 'America/New_York',

  // Layout
  layout: {
    direction: (process.env.NEXT_PUBLIC_DIR || 'ltr') as 'ltr' | 'rtl',
    sidebarDefaultOpen: true,
  },

  // API
  api: {
    baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000',
    timeout: 30000,
    retryAttempts: 3,
  },

  // Security
  security: {
    sessionTimeout: 15 * 60 * 1000, // 15 minutes
    enableDLP: true, // Data Loss Prevention
    enableMFA: true,
  },

  // Performance
  performance: {
    enableAnalytics: process.env.NODE_ENV === 'production',
    enableSentry: process.env.NODE_ENV === 'production',
  },
};
```

### Navigation Configuration

```typescript
// config/navigation.config.ts
export interface NavItem {
  label: string;
  href: string;
  icon: string;
  badge?: number;
  requiresAuth?: boolean;
  roles?: string[];
}

export const navigationConfig: NavItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: 'home',
    requiresAuth: true,
  },
  {
    label: 'Accounts',
    href: '/accounts',
    icon: 'wallet',
    requiresAuth: true,
  },
  {
    label: 'Transfers',
    href: '/transfers',
    icon: 'send',
    requiresAuth: true,
    roles: ['user', 'admin'],
  },
  {
    label: 'Settings',
    href: '/settings',
    icon: 'settings',
    requiresAuth: true,
  },
];
```

---

## Code Standards & Conventions

### Naming Conventions

```typescript
// Components
// PascalCase, descriptive, includes purpose
function TransferForm() {}
function AccountSelector() {}
function BalanceCard() {}

// Hooks
// camelCase, starts with 'use'
function useTransfer() {}
function useAccountBalance() {}
function useAuditLog() {}

// Services
// camelCase, ends with 'Service' or 'Helper'
const transferService = {}
const cryptoHelper = {}

// Types/Interfaces
// PascalCase, descriptive
interface Transfer {}
interface Account {}
type TransferStatus = 'PENDING' | 'COMPLETED' | 'FAILED';

// Variables
// camelCase, descriptive
const isLoading = false;
const hasError = true;
const transferHistory: Transfer[] = [];

// Constants
// UPPER_SNAKE_CASE
const MAX_TRANSFER_AMOUNT = 100000;
const API_TIMEOUT = 30000;
```

### Import Organization

```typescript
// 1. External libraries (React, Next.js, third-party)
import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';

// 2. Config & environment
import { appConfig } from '@/config/app.config';
import { env } from '@/env';

// 3. Absolute imports from src/ (organized by layer)
import { transferQueries } from '@/features/transfers/queries/transfer.queries';
import { useTransfer } from '@/features/transfers/hooks/useTransfer';
import { TransferSchema } from '@/features/transfers/schemas/transfer.schema';
import { Form, Field, Input } from '@/components/abstraction';
import { useAuditLog } from '@/hooks/useAuditLog';
import { cn } from '@/lib/utils';

// 4. Relative imports (from parent directories only)
import { TransferFormSkeleton } from './TransferFormSkeleton';

// Rules:
// ✅ Use absolute imports for anything in src/
// ❌ Don't use relative imports that go up more than 1 level: ../../../
// ❌ Never import from siblings' internal files
// ❌ No circular imports
```

### TypeScript Best Practices

```typescript
// 1. Strict mode - always enabled
{
  "compilerOptions": {
    "strict": true,
    "strictNullChecks": true,
    "noImplicitAny": true
  }
}

// 2. No 'any' type
// ❌ const user: any = {};
// ✅ const user: User = {};

// 3. Type union for states
type RequestState = 'idle' | 'loading' | 'success' | 'error';
const [state, setState] = useState<RequestState>('idle');

// 4. Use discriminated unions for complex data
type Result<T> = 
  | { success: true; data: T }
  | { success: false; error: string };

// 5. Generic types for reusable patterns
interface ApiResponse<T> {
  data: T | null;
  error: string | null;
}

// 6. Type inference where possible
const user = await fetchUser(); // Type inferred from return type
```

---

## Testing Strategy

### Unit Tests (Vitest)

```typescript
// features/transfers/__tests__/transfer.hook.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useTransfer } from '../hooks/useTransfer';
import * as actions from '@/app/actions/transfers.actions';

// Mock the Server Action
vi.mock('@/app/actions/transfers.actions');

describe('useTransfer', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient();
  });

  it('should execute transfer mutation', async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );

    const { result } = renderHook(() => useTransfer(), { wrapper });

    act(() => {
      result.current.mutate({
        recipientId: 'user-123',
        amount: 100,
        otp: '123456',
      });
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });
  });

  it('should handle mutation errors', async () => {
    vi.mocked(actions.executeTransferAction).mockRejectedValueOnce(
      new Error('Insufficient funds')
    );

    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );

    const { result } = renderHook(() => useTransfer(), { wrapper });

    // Act and assert...
  });
});
```

### Integration Tests (React Testing Library)

```typescript
// features/transfers/__tests__/TransferForm.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TransferForm } from '../components/TransferForm';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

describe('TransferForm', () => {
  it('should submit form with valid data', async () => {
    const queryClient = new QueryClient();
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={queryClient}>
        <TransferForm />
      </QueryClientProvider>
    );

    // Fill form
    await user.type(screen.getByLabelText(/amount/i), '100');
    await user.selectOptions(screen.getByLabelText(/recipient/i), 'user-123');

    // Submit
    await user.click(screen.getByRole('button', { name: /confirm/i }));

    // Assert success
    await waitFor(() => {
      expect(screen.getByText(/transfer completed/i)).toBeInTheDocument();
    });
  });

  it('should show validation error for invalid amount', async () => {
    const queryClient = new QueryClient();
    const user = userEvent.setup();

    render(
      <QueryClientProvider client={queryClient}>
        <TransferForm />
      </QueryClientProvider>
    );

    await user.type(screen.getByLabelText(/amount/i), '-100');
    await user.click(screen.getByRole('button', { name: /confirm/i }));

    await waitFor(() => {
      expect(screen.getByText(/amount must be positive/i)).toBeInTheDocument();
    });
  });
});
```

---

## Environment Variables

```env
# .env.local

# Feature Flags
NEXT_PUBLIC_ENABLE_BIOMETRIC=false
NEXT_PUBLIC_ENABLE_CRYPTO=false
NEXT_PUBLIC_BETA_UI=false
NEXT_PUBLIC_DIR=ltr
NEXT_PUBLIC_REGION=US

# API
NEXT_PUBLIC_API_URL=http://localhost:3000
NEXT_PUBLIC_WS_URL=ws://localhost:3000

# Auth
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=your-secret-here
JWT_SECRET=your-jwt-secret
REFRESH_TOKEN_SECRET=your-refresh-token-secret

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/bank_db

# Redis/Cache
REDIS_URL=redis://localhost:6379

# Security
ENCRYPTION_KEY=your-encryption-key

# Monitoring
SENTRY_DSN=your-sentry-dsn
NEXT_PUBLIC_ANALYTICS_ID=your-analytics-id

# Third-party integrations
STRIPE_SECRET_KEY=your-stripe-key
STRIPE_WEBHOOK_SECRET=your-webhook-secret
```

---

## Summary: Key Takeaways for LLM Code Generation

When using this document to generate code, follow these principles:

1. **Backend-Driven**: Most logic on server (Server Actions). Client is thin presentation layer.
2. **Type-Safe**: TypeScript strict mode. No `any` types. Leverage Zod for runtime validation.
3. **SRP Enforcement**: One responsibility per file. Clear separation: UI → Hooks → Services.
4. **Security First**: Validate server-side. Never trust client. Encrypt sensitive data. Audit everything.
5. **Performance**: RSC by default. Code split features. Minimize bundle size (< 200KB).
6. **Accessibility**: WCAG AAA. Semantic HTML. Keyboard navigation. ARIA labels.
7. **Real-time**: TanStack Query + Socket.io. Automatic invalidation. Optimistic updates.
8. **Error Handling**: Error boundaries + FeatureGuard wrappers. Never expose internal errors.
9. **Testing**: Unit tests (Vitest) + Integration tests (RTL). Test behavior, not implementation.
10. **Configuration**: Feature flags, environment-based config, easy to override for different environments.

---

**End of Architecture Guide**

This document is your reference for generating production-ready code that follows bank-grade standards.

