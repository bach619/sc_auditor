---
name: supabase
description: Supabase mastery — supabase-js v2, Auth, Realtime, Storage, Edge Functions, PostgreSQL schema design, Row Level Security, Next.js SSR, testing, and production deployment
license: MIT
compatibility: opencode
metadata:
  audience: fullstack-developers
  domain: backend
  paradigm: baas
  capabilities:
    - supabase-js-client
    - auth-magic-link-oauth
    - row-level-security
    - realtime-subscriptions
    - storage-management
    - edge-functions-deno
    - database-schema-design
    - migration-workflow
    - typed-client-generation
    - nextjs-ssr-integration
    - rls-policy-testing
    - connection-pooling
    - webhook-integration
    - image-transformation
  integrates_with:
    - frontend-react
    - frontend-svelte
    - backend-go
    - database-postgres
    - ai-rag
    - infra-observability
    - security-audit
    - workflow-general
---

# Skill: supabase

## Supabase Mastery — Full-Stack BaaS with PostgreSQL at Its Core

### Core Philosophy

Supabase is **open-source Firebase** built on PostgreSQL. Every feature — Auth, Realtime, Storage, Edge Functions — is a thin wrapper around Postgres primitives. Master the database, and you master Supabase.

---

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         SUPABASE ARCHITECTURE                            │
│                                                                          │
│  ┌──────────┐    ┌────────────┐    ┌───────────┐    ┌──────────────┐    │
│  │  Client   │───▶│ supabase-js │───▶│   API     │───▶│  PostgREST   │    │
│  │  (Web/    │    │   v2 SDK   │    │  Gateway  │    │  (REST→SQL)  │    │
│  │  Mobile)  │    │            │    │           │    │              │    │
│  └──────────┘    └────────────┘    └───────────┘    └──────┬───────┘    │
│       │                                                    │            │
│       │                    ┌───────────────────────────────┘            │
│       │                    │                                           │
│       │                    ▼                                           │
│       │           ┌────────────────┐                                  │
│       │           │  PostgreSQL 16  │──Extensions─────────────────┐   │
│       │           │  (Primary DB)   │  • pgvector (embeddings)    │   │
│       │           │                │  • postgis (spatial)         │   │
│       │           │                │  • pgcrypto (encryption)     │   │
│       │           │                │  • pg_stat_statements (perf) │   │
│       │           └────────────────┘  • pg_graphql (GraphQL)      │   │
│       │                    │         └────────────────────────────┘   │
│       │        ┌───────────┼───────────┐                             │
│       │        ▼           ▼           ▼                             │
│       │  ┌──────────┐┌──────────┐┌──────────┐                       │
│       │  │  Auth    ││ Realtime ││ Storage  │                       │
│       │  │ (GoTrue) ││(Realtime)││(S3-compat)│                      │
│       │  │ JWT +    ││ Broadcast││ Buckets   │                      │
│       │  │ OAuth    ││ Presence ││ RLS+ACL   │                      │
│       │  │ MagicLink││ PG Changes││ SignedURL │                      │
│       │  └──────────┘└──────────┘└──────────┘                       │
│       │                                                            │
│       │  ┌──────────────────────┐                                  │
│       └──│   Edge Functions     │                                  │
│          │   (Deno + TypeScript) │                                  │
│          │   Webhooks + Jobs    │                                  │
│          └──────────────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────┘
```

---

### 1. Database Schema Design

#### 1.1 Enabling Extensions

```sql
-- Run once per database
create extension if not exists "pgvector" with schema extensions;
create extension if not exists "postgis" with schema extensions;
create extension if not exists "pgcrypto" with schema extensions;
create extension if not exists "pg_stat_statements" with schema extensions;
create extension if not exists "pg_graphql" with schema extensions;
```

#### 1.2 Table Pattern (with RLS + Timestamps)

```sql
-- Every table should have: id, created_at, updated_at, created_by
create table public.projects (
    id          bigint generated always as identity primary key,
    uuid        uuid default gen_random_uuid() unique not null,
    name        text not null,
    slug        text unique not null,
    description text,
    created_by  uuid references auth.users(id) not null default auth.uid(),
    created_at  timestamptz default now() not null,
    updated_at  timestamptz default now() not null
);

-- Auto-update updated_at trigger
create extension if not exists "moddatetime" with schema extensions;

create trigger handle_updated_at before update on public.projects
    for each row execute function moddatetime(updated_at);
```

#### 1.3 Migrations (Supabase CLI)

```bash
# Create migration
supabase migration new add_projects_table

# Apply locally
supabase db reset

# Apply to linked project
supabase db push

# Generate types from schema
supabase gen types typescript --local > lib/database.types.ts
supabase gen types typescript --project-id <PROJECT_REF> > lib/database.types.ts
```

#### 1.4 Seed Data

```sql
-- supabase/seed.sql
insert into public.projects (name, slug, description, created_by)
values
    ('Carbon Monitoring', 'carbon-monitoring', 'Forest carbon MRV system', (select id from auth.users limit 1)),
    ('Community Map', 'community-map', 'Social forestry boundary mapping', (select id from auth.users limit 1));
```

#### 1.5 Views, Functions, and Materialized Views

```sql
-- View with user email join (safe via RLS)
create view public.project_summary with (security_invoker = true) as
select
    p.id,
    p.name,
    p.slug,
    count(t.id) as task_count,
    count(t.id) filter (where t.status = 'completed') as completed_count
from public.projects p
left join public.tasks t on t.project_id = p.id
group by p.id, p.name, p.slug;

-- Function with security definer (use sparingly)
create function public.get_my_projects()
returns setof public.projects
language sql
security definer
set search_path = public
as $$
    select *
    from public.projects
    where created_by = auth.uid()
    order by created_at desc;
$$;
```

---

### 2. Row Level Security (RLS)

#### 2.1 RLS Policy Chain

```
┌──────────────────────────────────────────────────────────────────────┐
│                      RLS POLICY EVALUATION                            │
│                                                                      │
│  Client sends JWT in Authorization: Bearer <token>                   │
│                                                                      │
│  ┌──────────────────────────────────────────┐                       │
│  │  1. Extract user_id + role from JWT      │                       │
│  │     auth.uid() = decoded.user_id          │                       │
│  │     auth.role() = 'authenticated'|'anon'  │                       │
│  └──────────────┬───────────────────────────┘                       │
│                 ▼                                                    │
│  ┌──────────────────────────────────────────┐                       │
│  │  2. Check table-level RLS enabled?        │                       │
│  │     YES → go to step 3                    │                       │
│  │     NO  → ALL ACCESS (danger)             │                       │
│  └──────────────┬───────────────────────────┘                       │
│                 ▼                                                    │
│  ┌──────────────────────────────────────────┐                       │
│  │  3. Evaluate ALL policies for operation   │                       │
│  │     (SELECT/INSERT/UPDATE/DELETE)         │                       │
│  │                                           │                       │
│  │     ┌─────────┐  ┌──────────┐  ┌───────┐ │                       │
│  │     │ User    │  │ Multi-   │  │ Admin │ │                       │
│  │     │ Owns    │  │ Tenant   │  │ Bypass│ │                       │
│  │     │ Records │  │ Check    │  │ Check │ │                       │
│  │     └─────────┘  └──────────┘  └───────┘ │                       │
│  │                                           │                       │
│  │  OR logic: ANY matching policy GRANTs     │                       │
│  └──────────────┬───────────────────────────┘                       │
│                 ▼                                                    │
│  ┌──────────────────────────────────────────┐                       │
│  │  4. Apply security barrier filters +      │                       │
│  │     Row-level WHERE clauses               │                       │
│  │                                           │                       │
│  │  RESULT: Filtered rows returned or denied │                       │
│  └──────────────────────────────────────────┘                       │
└──────────────────────────────────────────────────────────────────────┘
```

#### 2.2 Core Policy Patterns

```sql
-- ============================================================
-- PATTERN 1: User Owns Records (most common)
-- ============================================================
create policy "Users can read own profile"
    on public.profiles for select
    using (auth.uid() = id);

create policy "Users can update own profile"
    on public.profiles for update
    using (auth.uid() = id)
    with check (auth.uid() = id);

-- ============================================================
-- PATTERN 2: Multi-Tenant (organization-based)
-- ============================================================
create policy "Members can read org projects"
    on public.projects for select
    using (
        exists (
            select 1 from public.organization_members
            where organization_members.organization_id = projects.organization_id
            and organization_members.user_id = auth.uid()
        )
    );

-- ============================================================
-- PATTERN 3: Role-Based (admin, editor, viewer)
-- ============================================================
create policy "Admin can delete any project"
    on public.projects for delete
    using (
        exists (
            select 1 from public.profiles
            where profiles.id = auth.uid()
            and profiles.role = 'admin'
        )
    );

-- ============================================================
-- PATTERN 4: Authenticated vs Anon
-- ============================================================
create policy "Anyone can read public products"
    on public.products for select
    to anon, authenticated
    using (true);

create policy "Only members can create"
    on public.products for insert
    to authenticated
    with check (true);

-- ============================================================
-- PATTERN 5: Admin Bypass (service_role override)
-- ============================================================
-- NOTE: service_role key bypasses ALL RLS automatically.
-- Only use in Edge Functions or server-side, NEVER on client.
-- To create true admin bypass via RLS:
create policy "Admins can do anything"
    on public.projects for all
    using (
        (select role from public.profiles where id = auth.uid()) = 'admin'
    )
    with check (
        (select role from public.profiles where id = auth.uid()) = 'admin'
    );
```

#### 2.3 RLS Helper Functions

```sql
-- Get current user's role
create function public.current_user_role()
returns text
language sql
stable
as $$
    select coalesce(
        (select role from public.profiles where id = auth.uid()),
        'viewer'
    );
$$;

-- Check if user is member of organization
create function public.is_org_member(org_id bigint)
returns boolean
language sql
stable
as $$
    select exists (
        select 1 from public.organization_members
        where organization_id = org_id
        and user_id = auth.uid()
    );
$$;
```

---

### 3. Supabase Auth

#### 3.1 Auth Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                      SUPABASE AUTH FLOW                                 │
│                                                                        │
│  ┌──────────┐     ┌──────────────┐     ┌──────────────────────┐       │
│  │  Client   │     │ supabase-js  │     │   Supabase Auth      │       │
│  │           │     │              │     │   (GoTrue API)       │       │
│  └─────┬─────┘     └──────┬───────┘     └──────────┬───────────┘       │
│        │                  │                        │                    │
│        │  signInWithOtp() │                        │                    │
│        │─────────────────▶│                        │                    │
│        │                  │  POST /auth/v1/otp     │                    │
│        │                  │───────────────────────▶│                    │
│        │                  │                        │  Send email with   │
│        │                  │                        │  magic link / OTP  │
│        │                  │                        │◀── ─ ─ ─ ─ ─ ─    │
│        │                  │                        │                    │
│        │  [User clicks    │                        │                    │
│        │   magic link]    │                        │                    │
│        │                  │  GET /auth/v1/verify   │                    │
│        │                  │◀───────────────────────│                    │
│        │                  │  token_hash + type     │                    │
│        │                  │                        │                    │
│        │   setSession()   │                        │                    │
│        │◀─────────────────│                        │                    │
│        │                  │                        │                    │
│        │  ┌──────────────────────────────┐        │                    │
│        │  │  Session stored in:          │        │                    │
│        │  │  • localStorage (browser)    │        │                    │
│        │  │  • AsyncStorage (RN)         │        │                    │
│        │  │  • cookies (SSR/Next.js)     │        │                    │
│        │  └──────────────────────────────┘        │                    │
│        │                  │                        │                    │
│        │  [Token expires] │                        │                    │
│        │                  │  POST /auth/v1/token   │                    │
│        │                  │  refresh_token         │                    │
│        │                  │───────────────────────▶│                    │
│        │                  │                        │  Rotate tokens     │
│        │                  │  new access_token      │◀── ─ ─ ─ ─ ─ ─    │
│        │                  │◀───────────────────────│                    │
│        │                  │                        │                    │
│        │  onAuthStateChange('TOKEN_REFRESHED')    │                    │
│        │◀─────────────────────────────────────────│                    │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

#### 3.2 Email / Password Auth

```typescript
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)

// Sign up
const { data, error } = await supabase.auth.signUp({
  email: 'user@example.com',
  password: 'strong-password-123',
  options: {
    data: { full_name: 'User Example' },
    emailRedirectTo: `${location.origin}/auth/callback`,
  },
})

// Sign in
const { data, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'strong-password-123',
})

// Sign out
const { error } = await supabase.auth.signOut()

// Listen to auth state changes
supabase.auth.onAuthStateChange((event, session) => {
  switch (event) {
    case 'SIGNED_IN':
      console.log('User signed in', session?.user.id)
      break
    case 'SIGNED_OUT':
      console.log('User signed out')
      break
    case 'TOKEN_REFRESHED':
      console.log('Token refreshed')
      break
    case 'USER_UPDATED':
      console.log('User updated', session?.user)
      break
  }
})
```

#### 3.3 OAuth (Google, GitHub, etc.)

```typescript
// Sign in with Google
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'google',
  options: {
    redirectTo: `${location.origin}/auth/callback`,
    queryParams: {
      access_type: 'offline',
      prompt: 'consent',
    },
  },
})

// Sign in with GitHub
const { data, error } = await supabase.auth.signInWithOAuth({
  provider: 'github',
  options: {
    redirectTo: `${location.origin}/auth/callback`,
  },
})
```

#### 3.4 Magic Link

```typescript
const { data, error } = await supabase.auth.signInWithOtp({
  email: 'user@example.com',
  options: {
    emailRedirectTo: `${location.origin}/auth/callback`,
  },
})
```

#### 3.5 Phone Auth

```typescript
// Send OTP
const { data, error } = await supabase.auth.signInWithOtp({
  phone: '+6281234567890',
})

// Verify OTP
const { data, error } = await supabase.auth.verifyOtp({
  phone: '+6281234567890',
  token: '123456',
  type: 'sms',
})
```

#### 3.6 Session Management

```typescript
// Get current session
const { data: { session } } = await supabase.auth.getSession()

// Get current user
const { data: { user } } = await supabase.auth.getUser()

// Set session manually (from cookie / stored token)
const { data, error } = await supabase.auth.setSession({
  access_token: 'eyJ...',
  refresh_token: 'abc...',
})

// Refresh session
const { data, error } = await supabase.auth.refreshSession()
```

#### 3.7 User Management

```typescript
// Update user metadata
const { data, error } = await supabase.auth.updateUser({
  data: { full_name: 'New Name', avatar_url: 'https://...' },
})

// Update email
const { data, error } = await supabase.auth.updateUser({
  email: 'new-email@example.com',
})

// Reset password
const { data, error } = await supabase.auth.resetPasswordForEmail(
  'user@example.com',
  { redirectTo: `${location.origin}/auth/update-password` }
)
```

---

### 4. Realtime

#### 4.1 Realtime Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                      SUPABASE REALTIME                                  │
│                                                                        │
│  ┌──────────┐     ┌─────────────┐     ┌───────────────┐               │
│  │  Client   │────▶│ Realtime-js │────▶│  Realtime      │               │
│  │  (WS)     │     │  SDK        │     │  Server        │               │
│  └──────────┘     └─────────────┘     └───────┬───────┘               │
│                                                │                        │
│            ┌───────────────────────────────────┼────────┐              │
│            │            Channels                │        │              │
│            │  ┌────────────────┬───────────────┼────┐   │              │
│            │  │ Broadcast      │ Presence       │ PG │   │              │
│            │  │ (pub/sub, no   │ (who's online) │Changes│              │
│            │  │  persistence)  │                │      │              │
│            │  └────────────────┴────────────────┴──────┘              │
│            └───────────────────────────────────┼────────────────┘      │
│                                                │                        │
│                                                ▼                        │
│                                     ┌────────────────────┐             │
│                                     │  PostgreSQL WAL     │             │
│                                     │  (logical replication)           │
│                                     └────────────────────┘             │
└────────────────────────────────────────────────────────────────────────┘
```

#### 4.2 Postgres Changes (CDC)

```typescript
// Subscribe to database changes
const channel = supabase
  .channel('schema-db-changes')
  .on(
    'postgres_changes',
    {
      event: '*', // 'INSERT' | 'UPDATE' | 'DELETE' | '*'
      schema: 'public',
      table: 'projects',
      filter: `organization_id=eq.42`,
    },
    (payload) => {
      console.log('Change received!', payload)
      // payload.event_type: 'INSERT' | 'UPDATE' | 'DELETE'
      // payload.new: new row (for INSERT/UPDATE)
      // payload.old: old row (for UPDATE/DELETE)
    }
  )
  .subscribe()

// Cleanup
channel.unsubscribe()
```

#### 4.3 Broadcast (Pub/Sub)

```typescript
// Channel A — send
const channelA = supabase.channel('room-1')
channelA
  .subscribe((status) => {
    if (status === 'SUBSCRIBED') {
      channelA.send({
        type: 'broadcast',
        event: 'cursor-move',
        payload: { x: 100, y: 200, userId: 'abc' },
      })
    }
  })

// Channel B — receive
const channelB = supabase.channel('room-1')
channelB
  .on('broadcast', { event: 'cursor-move' }, (payload) => {
    console.log('Cursor moved', payload)
  })
  .subscribe()
```

#### 4.4 Presence (Who's Online)

```typescript
const channel = supabase.channel('room-1')

const presenceTrack = channel
  .on('presence', { event: 'sync' }, () => {
    const state = channel.presenceState()
    console.log('Online users:', state)
  })
  .on('presence', { event: 'join' }, ({ key, newPresences }) => {
    console.log('Joined:', newPresences)
  })
  .on('presence', { event: 'leave' }, ({ key, leftPresences }) => {
    console.log('Left:', leftPresences)
  })
  .subscribe(async (status) => {
    if (status === 'SUBSCRIBED') {
      await channel.track({
        user_id: user.id,
        online_at: new Date().toISOString(),
      })
    }
  })
```

#### 4.5 Realtime Cleanup (Critical)

```typescript
// ALWAYS unsubscribe when component unmounts
useEffect(() => {
  const channel = supabase
    .channel('my-channel')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'tasks' }, () => {})
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}, [])
```

---

### 5. Storage

#### 5.1 Bucket Setup

```sql
-- Create bucket (via dashboard or SQL)
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', false);

insert into storage.buckets (id, name, public)
values ('documents', 'documents', false);
```

#### 5.2 Storage RLS

```sql
-- Allow authenticated users to upload their own avatar
create policy "Users can upload their own avatar"
    on storage.objects for insert
    with check (
        bucket_id = 'avatars'
        and auth.role() = 'authenticated'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- Allow users to read their own avatar
create policy "Users can read their own avatar"
    on storage.objects for select
    using (
        bucket_id = 'avatars'
        and auth.role() = 'authenticated'
        and (storage.foldername(name))[1] = auth.uid()::text
    );

-- Public bucket for shared content
create policy "Anyone can read public documents"
    on storage.objects for select
    using (bucket_id = 'public-assets');
```

#### 5.3 Upload Files

```typescript
// Upload with upsert
const { data, error } = await supabase.storage
  .from('avatars')
  .upload(`${user.id}/profile.jpg`, file, {
    cacheControl: '3600',
    upsert: true,
    contentType: 'image/jpeg',
  })

// Upload from URL (via Edge Function)
// Browser upload with progress
const { data, error } = await supabase.storage
  .from('documents')
  .upload(`reports/${file.name}`, file, {
    cacheControl: '86400',
    upsert: false,
    duplex: 'half',
  })
```

#### 5.4 Download & Signed URLs

```typescript
// Public URL (only works for public buckets)
const { data } = supabase.storage
  .from('public-assets')
  .getPublicUrl('hero-bg.jpg')
// data.publicUrl: "https://<project>.supabase.co/storage/v1/object/public/public-assets/hero-bg.jpg"

// Signed URL (time-limited, works for private buckets)
const { data, error } = await supabase.storage
  .from('documents')
  .createSignedUrl('reports/q1-2026.pdf', 3600) // 1 hour
// data.signedUrl: "https://<project>.supabase.co/storage/v1/object/sign/documents/reports/..."

// Download file
const { data, error } = await supabase.storage
  .from('avatars')
  .download(`${user.id}/profile.jpg`)
```

#### 5.5 Image Transformation

```typescript
// Transform on-the-fly via URL parameters
// Requires Supabase Image Transformation add-on

// Original: /storage/v1/object/public/avatars/user123/profile.jpg

// Resize to 200x200
// /storage/v1/object/public/avatars/user123/profile.jpg?width=200&height=200&resize=cover

// Quality 50%, WebP format
// /storage/v1/object/public/avatars/user123/profile.jpg?quality=50&format=webp

// Using supabase-js helper (manual string concatenation)
const url = supabase.storage.from('avatars').getPublicUrl(`${user.id}/profile.jpg`).data.publicUrl
const transformed = `${url}?width=200&height=200&resize=cover&format=webp`
```

#### 5.6 List, Move, Delete

```typescript
// List files in a folder
const { data, error } = await supabase.storage
  .from('documents')
  .list('reports', {
    limit: 100,
    offset: 0,
    sortBy: { column: 'created_at', order: 'desc' },
  })

// Move / rename
const { error } = await supabase.storage
  .from('documents')
  .move('reports/draft.pdf', 'reports/final.pdf')

// Copy
const { error } = await supabase.storage
  .from('documents')
  .copy('reports/draft.pdf', 'reports/draft-backup.pdf')

// Delete
const { error } = await supabase.storage
  .from('documents')
  .remove(['reports/old-report.pdf'])
```

---

### 6. Edge Functions

#### 6.1 Edge Function Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                    SUPABASE EDGE FUNCTIONS                              │
│                                                                        │
│  ┌──────────┐     ┌─────────────────┐     ┌─────────────────────┐     │
│  │  Client   │────▶│  Supabase API    │────▶│  Deno Runtime       │     │
│  │           │     │  Gateway         │     │  (V8 Isolate)       │     │
│  └──────────┘     │  POST /functions/v1/   │                     │     │
│                   └─────────────────┘     │  ┌───────────────┐  │     │
│                                            │  │  supabase-js  │  │     │
│                                            │  │  (service_key)│  │     │
│                                            │  └───────┬───────┘  │     │
│                                            └──────────┼──────────┘     │
│                                                       │                │
│                                                       ▼                │
│                                            ┌─────────────────────┐     │
│                                            │   Database via       │     │
│                                            │   service_role       │     │
│                                            │   (RLS bypass)       │     │
│                                            └─────────────────────┘     │
└────────────────────────────────────────────────────────────────────────┘
```

#### 6.2 Basic Edge Function

```typescript
// supabase/functions/send-notification/index.ts
import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { user_id, message } = await req.json()

  // Insert notification with service_role (bypasses RLS)
  const { error } = await supabase.from('notifications').insert({
    user_id,
    message,
    created_at: new Date().toISOString(),
  })

  if (error) {
    return new Response(JSON.stringify({ error: error.message }), {
      status: 400,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  return new Response(JSON.stringify({ success: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
})
```

#### 6.3 Webhook Receiver

```typescript
// supabase/functions/stripe-webhook/index.ts
import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const signature = req.headers.get('stripe-signature')
  if (!signature) {
    return new Response('Unauthorized', { status: 401 })
  }

  const body = await req.text()
  // Verify webhook signature with Stripe SDK...

  const event = JSON.parse(body)
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  switch (event.type) {
    case 'checkout.session.completed': {
      const session = event.data.object
      await supabase.from('subscriptions').upsert({
        user_id: session.client_reference_id,
        stripe_session_id: session.id,
        status: 'active',
        amount: session.amount_total,
      })
      break
    }
  }

  return new Response(JSON.stringify({ received: true }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
})
```

#### 6.4 Background Jobs (Scheduled)

```typescript
// supabase/functions/cleanup-expired/index.ts
// Configure via Dashboard: Edge Functions > schedule > "0 0 * * *" (daily)

import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async () => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { error } = await supabase
    .from('sessions')
    .delete()
    .lt('expires_at', new Date().toISOString())

  return new Response(JSON.stringify({ deleted: error ? 0 : 'done' }), {
    headers: { 'Content-Type': 'application/json' },
  })
})
```

#### 6.5 Edge Function Configuration

```bash
# Deploy function
supabase functions deploy send-notification --no-verify-jwt

# Set secrets
supabase secrets set STRIPE_SECRET_KEY=sk_test_...
supabase secrets set SENDGRID_API_KEY=SG....

# List secrets
supabase secrets list

# Run locally
supabase functions serve send-notification --env-file .env.local
```

---

### 7. Client Library Patterns

#### 7.1 Typed Client with Generated Types

```typescript
import { createClient } from '@supabase/supabase-js'
import type { Database } from '@/lib/database.types'

// Typed client — full autocomplete for tables, columns, joins
export const supabase = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

#### 7.2 Query Builder

```typescript
// Select with filter
const { data, error } = await supabase
  .from('projects')
  .select('id, name, slug, created_at')
  .eq('organization_id', orgId)
  .order('created_at', { ascending: false })
  .limit(10)
  .returns<Project[]>()

// Single row
const { data, error } = await supabase
  .from('profiles')
  .select('*')
  .eq('id', userId)
  .single()

// Count
const { count, error } = await supabase
  .from('tasks')
  .select('*', { count: 'exact', head: true })
  .eq('status', 'pending')
```

#### 7.3 Filters

```typescript
// Comparison operators
supabase.from('projects').eq('status', 'active')       // =
supabase.from('projects').neq('status', 'archived')    // !=
supabase.from('projects').gt('budget', 1000000)        // >
supabase.from('projects').gte('created_at', '2026-01-01') // >=
supabase.from('projects').lt('budget', 500000)         // <
supabase.from('projects').lte('created_at', '2026-06-01') // <=

// Text search
supabase.from('projects').like('name', '%carbon%')     // LIKE
supabase.from('projects').ilike('name', '%Carbon%')    // ILIKE (case-insensitive)

// Array operators
supabase.from('projects').in('status', ['active', 'pending'])
supabase.from('projects').contains('tags', ['forestry'])  // @> array
supabase.from('projects').containedBy('tags', ['forestry', 'carbon']) // <@ array
supabase.from('projects').overlaps('tags', ['forestry', 'monitoring']) // &&

// Null checks
supabase.from('projects').is('deleted_at', null)
supabase.from('projects').not('deleted_at', 'is', null)

// Logical grouping
supabase
  .from('projects')
  .or('status.eq.active,status.eq.pending')
  .filter('budget', 'gte', 1000000)
```

#### 7.4 Pagination

```typescript
// Offset-based (simple, inefficient for large datasets)
const page = 1
const pageSize = 20
const { data, error, count } = await supabase
  .from('projects')
  .select('*', { count: 'exact' })
  .range((page - 1) * pageSize, page * pageSize - 1)
  .order('created_at', { ascending: false })

// Cursor-based (preferred for infinite scroll)
const cursor = '2026-05-01T00:00:00Z' // last item's created_at
const { data } = await supabase
  .from('projects')
  .select('*')
  .lt('created_at', cursor) // cursor from last item
  .order('created_at', { ascending: false })
  .limit(20)
```

#### 7.5 Joins (via foreign keys)

```typescript
// One-to-many join (automatically inferred from FK)
const { data, error } = await supabase
  .from('organizations')
  .select(`
    id,
    name,
    projects (
      id,
      name,
      status
    )
  `)
  .eq('id', orgId)
  .single()

// Many-to-one (reverse relationship)
const { data } = await supabase
  .from('tasks')
  .select(`
    id,
    title,
    assignee:user_id (
      id,
      full_name,
      avatar_url
    )
  `)

// Custom join with filters on nested resource
const { data } = await supabase
  .from('organizations')
  .select(`
    id,
    name,
    projects!inner (
      id,
      name,
      tasks (
        id,
        title
      )
    )
  `) // !inner = only orgs that have projects
  .eq('projects.status', 'active')
```

#### 7.6 Upsert and Insert

```typescript
// Single insert
const { data, error } = await supabase
  .from('profiles')
  .insert({
    id: user.id,
    full_name: 'User Example',
    avatar_url: 'https://...',
  })
  .select()
  .single()

// Bulk insert
const { data, error } = await supabase
  .from('tasks')
  .insert([
    { project_id: 1, title: 'Task 1', status: 'pending' },
    { project_id: 1, title: 'Task 2', status: 'pending' },
    { project_id: 1, title: 'Task 3', status: 'pending' },
  ])
  .select()

// Upsert (insert or update by conflict column)
const { data, error } = await supabase
  .from('profiles')
  .upsert(
    { id: user.id, full_name: 'Updated Name' },
    { onConflict: 'id', ignoreDuplicates: false }
  )
  .select()

// Update
const { data, error } = await supabase
  .from('projects')
  .update({ status: 'completed', updated_at: new Date().toISOString() })
  .eq('id', projectId)
  .select()

// Delete
const { error } = await supabase
  .from('tasks')
  .delete()
  .eq('id', taskId)
```

#### 7.7 Batch Operations

```typescript
// supabase-js does NOT support multi-statement transactions natively.
// Use PostgreSQL functions + rpc() for atomic operations:

const { data, error } = await supabase.rpc('create_project_with_tasks', {
  project_name: 'New Project',
  task_titles: ['Task A', 'Task B'],
})

// Or use PostgREST batch endpoint (single connection):
// POST /rest/v1/rpc/create_project_with_tasks
```

---

### 8. Next.js + Supabase

#### 8.1 SSR Client Setup

```typescript
// lib/supabase/server.ts — Server Component client
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export function createClient() {
  const cookieStore = cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        },
      },
    }
  )
}
```

```typescript
// lib/supabase/client.ts — Browser client
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
}
```

```typescript
// lib/supabase/actions.ts — Server Action client
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export function createClient() {
  const cookieStore = cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value, options }) =>
            cookieStore.set(name, value, options)
          )
        },
      },
    }
  )
}
```

#### 8.2 Auth Middleware

```typescript
// middleware.ts
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function middleware(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  const { data: { user } } = await supabase.auth.getUser()

  // Protected routes
  if (!user && !request.nextUrl.pathname.startsWith('/auth')) {
    const url = request.nextUrl.clone()
    url.pathname = '/auth/login'
    return NextResponse.redirect(url)
  }

  // Redirect authenticated users away from auth pages
  if (user && request.nextUrl.pathname.startsWith('/auth')) {
    const url = request.nextUrl.clone()
    url.pathname = '/dashboard'
    return NextResponse.redirect(url)
  }

  return supabaseResponse
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
```

#### 8.3 Auth Callback Route

```typescript
// app/auth/callback/route.ts
import { createServerClient } from '@supabase/ssr'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function GET(request: NextRequest) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const next = searchParams.get('next') ?? '/dashboard'

  if (code) {
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
      {
        cookies: {
          getAll() { return request.cookies.getAll() },
          setAll(cookiesToSet) {
            cookiesToSet.forEach(({ name, value }) =>
              request.cookies.set(name, value)
            )
          },
        },
      }
    )

    const { error } = await supabase.auth.exchangeCodeForSession(code)
    if (!error) {
      return NextResponse.redirect(`${origin}${next}`)
    }
  }

  return NextResponse.redirect(`${origin}/auth/auth-code-error`)
}
```

#### 8.4 Server Component Query

```typescript
// app/dashboard/page.tsx
import { createClient } from '@/lib/supabase/server'
import { redirect } from 'next/navigation'

export default async function DashboardPage() {
  const supabase = createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) redirect('/auth/login')

  const { data: projects } = await supabase
    .from('projects')
    .select('id, name, slug, status, created_at')
    .eq('created_by', user.id)
    .order('created_at', { ascending: false })

  return (
    <div>
      <h1>My Projects</h1>
      <pre>{JSON.stringify(projects, null, 2)}</pre>
    </div>
  )
}
```

#### 8.5 Server Action

```typescript
// app/projects/actions.ts
'use server'

import { createClient } from '@/lib/supabase/actions'
import { revalidatePath } from 'next/cache'
import { z } from 'zod'

const projectSchema = z.object({
  name: z.string().min(1).max(100),
  description: z.string().max(1000).optional(),
})

export async function createProject(formData: FormData) {
  const supabase = createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Unauthorized')

  const parsed = projectSchema.parse({
    name: formData.get('name'),
    description: formData.get('description'),
  })

  const { error } = await supabase.from('projects').insert({
    name: parsed.name,
    slug: parsed.name.toLowerCase().replace(/\s+/g, '-'),
    description: parsed.description,
    created_by: user.id,
  })

  if (error) throw new Error(error.message)

  revalidatePath('/dashboard')
}

export async function deleteProject(projectId: number) {
  const supabase = createClient()

  const { error } = await supabase
    .from('projects')
    .delete()
    .eq('id', projectId)

  if (!error) revalidatePath('/dashboard')
}
```

#### 8.6 Route Handler

```typescript
// app/api/projects/route.ts
import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET() {
  const supabase = createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const { data, error } = await supabase
    .from('projects')
    .select('*')
    .eq('created_by', user.id)

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 })
  }

  return NextResponse.json(data)
}

export async function POST(request: Request) {
  const supabase = createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()

  const { data, error } = await supabase
    .from('projects')
    .insert({ ...body, created_by: user.id })
    .select()
    .single()

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 400 })
  }

  return NextResponse.json(data, { status: 201 })
}
```

---

### 9. Testing

#### 9.1 Local Development

```bash
# Start local Supabase stack
supabase start

# Check status
supabase status

# Reset database to clean state
supabase db reset

# Run migrations
supabase db push

# View local dashboard
# http://localhost:54323

# Stop
supabase stop
```

#### 9.2 RLS Testing with SQL

```sql
-- Test RLS policies directly in SQL editor
-- Run as authenticated user simulation

-- Test: authenticated user can read own profile
select * from public.profiles
where id = auth.uid();

-- Test: anon user cannot read profiles
-- (Run this in a separate session with anon role)
set local role anon;
select * from public.profiles;
-- Should return empty or error

-- Test: user cannot read other users' private data
select * from public.projects
where created_by != auth.uid();
-- Should return empty if RLS is correct

-- Test: insert with RLS check
insert into public.projects (name, slug, created_by)
values ('Test', 'test', '00000000-0000-0000-0000-000000000000');
-- Should fail — created_by doesn't match auth.uid()
```

#### 9.3 RLS Testing with TypeScript

```typescript
import { createClient } from '@supabase/supabase-js'
import type { Database } from '@/lib/database.types'

// Test helper: create authenticated client
function authedClient(userId: string, userEmail: string) {
  // This is a simplified approach — in production use test helpers
  // or a dedicated test library
  const supabase = createClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
  return supabase
}

// Test: user can only see their own projects
async function testUserIsolation() {
  const supabase = createClient<Database>(
    process.env.SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY! // bypass RLS for setup
  )

  // Create test users and data via service_role
  const { data: userA } = await supabase.auth.admin.createUser({
    email: 'test-a@example.com',
    password: 'test123',
    email_confirm: true,
  })

  const { data: userB } = await supabase.auth.admin.createUser({
    email: 'test-b@example.com',
    password: 'test123',
    email_confirm: true,
  })

  // Sign in as user A and check isolation
  const clientA = createClient<Database>(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  )
  await clientA.auth.signInWithPassword({
    email: 'test-a@example.com',
    password: 'test123',
  })

  const { data: projectsA } = await clientA
    .from('projects')
    .select('*')

  // User A should only see projects owned by user A
  const allOwnedByA = projectsA?.every(p => p.created_by === userA.user?.id)
  console.assert(allOwnedByA, 'User A saw projects not owned by them')
}
```

#### 9.4 Test Containers (Optional)

```typescript
// Separate test project — never test on production!
// Use `supabase projects create` for a dedicated test project
// or use `supabase db dump` + `supabase db push` for CI
```

---

### 10. Performance

#### 10.1 Connection Pooling (PgBouncer)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CONNECTION POOLING (PgBouncer)                        │
│                                                                        │
│  ┌──────────┐                                                         │
│  │  Client  │──┐                                                      │
│  ├──────────┤  │                                                      │
│  │  Client  │──┤    ┌──────────────┐    ┌──────────────────┐          │
│  ├──────────┤  │    │  Supabase     │    │  PgBouncer       │          │
│  │  Client  │──┼───▶│  Pooler       │───▶│  (Transaction    │          │
│  ├──────────┤  │    │  (port 6543)  │    │   Pooling Mode)  │          │
│  │  Client  │──┘    └──────────────┘    └────────┬─────────┘          │
│  └──────────┘                                     │                    │
│                                                    ▼                    │
│                                          ┌──────────────────┐          │
│                                          │  PostgreSQL 16    │          │
│                                          │  (max_connections │          │
│                                          │   = 15 default)   │          │
│                                          └──────────────────┘          │
│                                                                        │
│  • Port 5432 = direct (for migrations, admin)                         │
│  • Port 6543 = pooled (for applications, serverless)                  │
│  • Transaction mode: connection released after each transaction       │
│  • Session mode: NEVER use session mode with Supabase                 │
└────────────────────────────────────────────────────────────────────────┘
```

```typescript
// Always use port 6543 for application connections
const supabase = createClient(
  'https://<project>.supabase.co', // or your custom domain
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
// The SDK automatically uses the pooler when connecting through the API
```

#### 10.2 Query Optimization

```sql
-- Use EXPLAIN ANALYZE to find slow queries
explain analyze
select * from projects
where organization_id = 42
order by created_at desc
limit 20;

-- Create indexes for common query patterns
create index idx_projects_org_created
    on public.projects (organization_id, created_at desc);

create index idx_projects_status
    on public.projects (status)
    where status in ('active', 'pending'); -- partial index

-- Use covering indexes for frequent queries
create index idx_projects_list
    on public.projects (organization_id, created_at desc)
    include (id, name, slug, status);

-- Avoid expensive operations
-- BAD: full-text search on unindexed column
select * from projects where name like '%' || ? || '%';

-- GOOD: use trigram index
create extension if not exists "pg_trgm" with schema extensions;
create index idx_projects_name_trgm on projects using gin (name gin_trgm_ops);
select * from projects where name ilike '%' || ? || '%';
```

#### 10.3 Caching Strategies

```typescript
// Client-side caching with React Query (TanStack Query)
import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase/client'

function useProjects(orgId: number) {
  return useQuery({
    queryKey: ['projects', orgId],
    queryFn: async () => {
      const { data } = await supabase
        .from('projects')
        .select('id, name, slug, status')
        .eq('organization_id', orgId)
        .order('created_at', { ascending: false })

      return data ?? []
    },
    staleTime: 30_000, // 30 seconds before refetch
    gcTime: 5 * 60_000, // 5 minutes in cache
  })
}

// Supabase local cache (auto-enabled)
// supabase-js v2 caches auth session in localStorage automatically.
// Database queries are NOT cached by default — use React Query.

// Server-side: Next.js data cache
async function getProjects() {
  const supabase = createClient()
  const { data } = await supabase.from('projects').select('*')

  return data ?? []
}

// In a Server Component, Next.js caches by default (fetch-based)
// supabase-js uses fetch internally, so it benefits from:
// - fetch cache (force-cache by default)
// - revalidation with revalidatePath / revalidateTag
```

#### 10.4 Large Dataset Handling

```typescript
// Use streaming for large datasets
// supabase-js does NOT support streaming natively — use cursor pagination

// For very large exports, use Edge Functions + CSV streaming
// supabase/functions/export-csv/index.ts
import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

serve(async (req) => {
  const supabase = createClient(
    Deno.env.get('SUPABASE_URL')!,
    Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
  )

  const { rows } = await req.json()
  let cursor = 0
  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    async pull(controller) {
      const { data } = await supabase
        .from('projects')
        .select('*')
        .range(cursor, cursor + rows - 1)
        .order('id')

      if (!data?.length) {
        controller.close()
        return
      }

      controller.enqueue(encoder.encode(JSON.stringify(data) + '\n'))
      cursor += rows
    },
  })

  return new Response(stream, {
    headers: { 'Content-Type': 'application/jsonl' },
  })
})
```

---

### 11. Security

#### 11.1 RLS Review Checklist

```
□  Every table has RLS enabled: ALTER TABLE ... ENABLE ROW LEVEL SECURITY;
□  Every bucket has RLS enabled
□  No table has a default-permissive policy:  USING (true) without restriction
□  service_role key is NEVER used on client-side
□  anon key has minimal privileges (only what public needs)
□  All auth helpers: auth.uid(), auth.email(), auth.role() used correctly
□  WITH CHECK clause matches USING clause on UPDATE policies
□  Function has proper search_path set (prevents search-path injection)
□  No SQL injection vectors in RLS policies (avoid dynamic SQL)
□  RLS policies tested with both authenticated and anon roles
□  Storage policies protect both SELECT and INSERT/UPDATE/DELETE
□  Email confirmation required for signup (default: on)
□  Rate limiting configured for auth endpoints
```

#### 11.2 Environment Variables

```bash
# .env.local — NEVER commit to repository
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_DB_PASSWORD=your-db-password

# For Edge Functions
# Set via: supabase secrets set KEY=value
# Deno.env.get('STRIPE_SECRET_KEY')
```

#### 11.3 CORS Configuration

```typescript
// In Supabase Dashboard > API > Settings
// Or via Management API

// Allowed Origins (for production):
// https://yourdomain.com
// https://www.yourdomain.com
// http://localhost:3000 (dev only)

// For Edge Functions, set per-function or global:
supabase functions deploy my-function --import-map ./import_map.json
```

#### 11.4 Service Key Protection Rules

```
┌────────────────────────────────────────────────────────────────────────┐
│                    SERVICE KEY USAGE RULES                              │
│                                                                        │
│  ✅ DO use service_role key in:                                        │
│     • Edge Functions (server-side only)                                │
│     • Server Actions (Next.js)                                         │
│     • Route Handlers (Next.js API routes)                              │
│     • Scheduled / background jobs                                      │
│     • Admin operations (user management, migrations)                   │
│                                                                        │
│  ❌ NEVER use service_role key in:                                     │
│     • Browser / client-side code                                       │
│     • Mobile app bundles                                               │
│     • Public repositories                                              │
│     • Environment variables prefixed with NEXT_PUBLIC_                 │
│     • Client-side API calls                                            │
│                                                                        │
│  ⚠ service_role bypasses ALL RLS — treat it as database admin access   │
└────────────────────────────────────────────────────────────────────────┘
```

#### 11.5 Webhook Security

```typescript
// Always verify webhook signatures
// supabase/functions/stripe-webhook/index.ts
import Stripe from 'https://esm.sh/stripe@14'

const stripe = new Stripe(Deno.env.get('STRIPE_SECRET_KEY')!, {
  apiVersion: '2024-12-18',
})

serve(async (req) => {
  const body = await req.text()
  const sig = req.headers.get('stripe-signature')!

  let event: Stripe.Event
  try {
    event = stripe.webhooks.constructEvent(
      body,
      sig,
      Deno.env.get('STRIPE_WEBHOOK_SECRET')!
    )
  } catch {
    return new Response('Invalid signature', { status: 400 })
  }

  // Process event...
})
```

---

### 12. File Convention

```
project-root/
├── lib/
│   ├── supabase/
│   │   ├── client.ts          # Browser client (createBrowserClient)
│   │   ├── server.ts          # Server Component client (createServerClient)
│   │   ├── actions.ts         # Server Action client (createServerClient)
│   │   ├── middleware.ts      # Auth middleware configuration
│   │   └── admin.ts           # Service-role client (admin operations)
│   └── database.types.ts      # Generated types from `supabase gen types`
│
├── middleware.ts              # Next.js auth middleware at root
│
├── app/
│   ├── auth/
│   │   ├── login/
│   │   │   └── page.tsx       # Login page
│   │   ├── callback/
│   │   │   └── route.ts       # OAuth callback route handler
│   │   └── confirm/
│   │       └── route.ts       # Email verification route
│   └── [protected]/
│       └── page.tsx           # Protected pages with server-side auth check
│
├── supabase/
│   ├── config.toml            # Supabase local config
│   ├── migrations/            # Database migrations
│   │   ├── 20250101000000_add_projects.sql
│   │   └── 20250102000000_add_rls_policies.sql
│   ├── seed.sql               # Seed data for local dev
│   └── functions/             # Edge Functions
│       ├── send-notification/
│       │   └── index.ts
│       └── stripe-webhook/
│           └── index.ts
│
└── .env.example               # Template (never commit real keys)
```

---

### 13. Anti-Patterns

#### ❌ Disabling RLS

```sql
-- NEVER do this in production
alter table public.projects disable row level security;

-- Instead: create proper RLS policies
alter table public.projects enable row level security;
create policy "Users can read own projects"
    on public.projects for select
    using (created_by = auth.uid());
```

#### ❌ Using Service Key on Client

```typescript
// ❌ BAD — service_role key leaked to client
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY! // LEAKED!
)

// ✅ GOOD — use anon key on client, service key only on server
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
)
```

#### ❌ Ignoring Realtime Cleanup

```typescript
// ❌ BAD — memory leak on every mount
useEffect(() => {
  supabase
    .channel('my-channel')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'tasks' }, handler)
    .subscribe()
  // No cleanup!
}, [])

// ✅ GOOD — unsubscribe on unmount
useEffect(() => {
  const channel = supabase
    .channel('my-channel')
    .on('postgres_changes', { event: '*', schema: 'public', table: 'tasks' }, handler)
    .subscribe()

  return () => {
    supabase.removeChannel(channel)
  }
}, [])
```

#### ❌ Exposing Internal IDs

```typescript
// ❌ BAD — exposing auto-increment IDs in URLs
const { data } = await supabase.from('projects').select('id') // id = 42
// URL: /projects/42 — user can guess other IDs

// ✅ GOOD — use UUID or slug
const { data } = await supabase.from('projects').select('uuid, slug')
// URL: /projects/a1b2c3d4-... or /projects/carbon-monitoring
```

#### ❌ Overfetching in Server Components

```typescript
// ❌ BAD — fetching entire row when only name needed
const { data } = await supabase.from('projects').select('*')
// Returns all columns including large text fields

// ✅ GOOD — select only needed columns
const { data } = await supabase
  .from('projects')
  .select('id, name, slug')
```

#### ❌ No Error Handling

```typescript
// ❌ BAD — ignoring errors
const { data } = await supabase.from('projects').insert({ name })
console.log(data) // data might be null, error silently lost

// ✅ GOOD — handle errors
const { data, error } = await supabase.from('projects').insert({ name })
if (error) {
  console.error('Failed to create project:', error.message)
  throw new Error(error.message)
}
// Use data...
```

#### ❌ N+1 Queries

```typescript
// ❌ BAD — N+1: fetching org then projects separately
const orgs = await supabase.from('organizations').select('*')
for (const org of orgs.data ?? []) {
  const projects = await supabase
    .from('projects')
    .select('*')
    .eq('organization_id', org.id)
}

// ✅ GOOD — use joins (supabase-js resolves FK relationships)
const { data } = await supabase
  .from('organizations')
  .select(`
    *,
    projects (*)
  `)
```

---

### 14. Implementation Checklist

#### Database & Schema
- [ ] Enable required extensions (pgvector, postgis, pgcrypto, pg_stat_statements)
- [ ] Create tables with proper FKs, indexes, timestamps
- [ ] Add `created_by` foreign key to `auth.users` on every entity table
- [ ] Generate and apply initial migration
- [ ] Add seed data for local development
- [ ] Generate TypeScript types: `supabase gen types typescript`
- [ ] Create helper views and functions (with `security_invoker = true`)

#### RLS
- [ ] Enable RLS on ALL tables: `alter table ... enable row level security`
- [ ] Write SELECT policy (read own / read org-scoped)
- [ ] Write INSERT policy (create with auth.uid() as owner)
- [ ] Write UPDATE policy (USING + WITH CHECK with matching conditions)
- [ ] Write DELETE policy (owner or admin only)
- [ ] Write storage RLS policies for every bucket
- [ ] Test each policy with authenticated and anon roles
- [ ] Test boundary cases: cross-tenant access, unauthenticated access

#### Auth
- [ ] Choose auth method: email + password, OAuth, magic link, phone
- [ ] Configure OAuth providers (Google, GitHub) in Dashboard
- [ ] Set email redirect URLs
- [ ] Create auth callback route (/auth/callback)
- [ ] Set up auth middleware (Next.js middleware.ts)
- [ ] Create login / signup pages
- [ ] Create profile table with `id` referencing `auth.users`
- [ ] Set up trigger to auto-create profile on signup
- [ ] Test session persistence across page refreshes

#### Realtime
- [ ] Subscribe to relevant tables via `postgres_changes`
- [ ] Implement cleanup (unsubscribe on unmount / dispose)
- [ ] Use broadcast for ephemeral events (cursor, typing indicator)
- [ ] Use presence for "who's online" features
- [ ] Set proper RLS for Realtime (replication in publication)

#### Storage
- [ ] Create buckets (public / private based on use case)
- [ ] Write storage RLS policies
- [ ] Implement upload UI with progress
- [ ] Use signed URLs for private files
- [ ] Set up image transformation if needed
- [ ] Test file type and size restrictions (via RLS or client)

#### Edge Functions
- [ ] Write and test first function locally
- [ ] Set environment secrets
- [ ] Deploy: `supabase functions deploy`
- [ ] Configure JWT verification (or skip for webhooks)
- [ ] Set up scheduled functions for background jobs
- [ ] Add error handling and logging

#### Next.js Integration
- [ ] Set up lib/supabase/client.ts, server.ts, actions.ts
- [ ] Configure middleware.ts for auth protection
- [ ] Add auth callback route
- [ ] Implement server component data fetching with auth check
- [ ] Implement server actions with auth validation
- [ ] Add route handlers for external API consumption
- [ ] Set up CORS for production domain

#### Testing & Deployment
- [ ] `supabase start` — verify everything works locally
- [ ] `supabase db push` — push to staging/production
- [ ] Run RLS tests with both authenticated and anon roles
- [ ] Check Supabase Dashboard for any errors or slow queries
- [ ] Verify environment variables in production
- [ ] Set up monitoring (Supabase logs, Sentry, etc.)
- [ ] Configure custom domain and SSL
- [ ] Set up database backups (Point-in-Time Recovery)
- [ ] Document API endpoints and RLS policies
