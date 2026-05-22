---
name: i18n
description: >
  Internationalization (i18n) mastery: next-intl v4, i18next v23+/v24+, react-i18next, 
  vue-i18n, svelte-i18n. Translation management, ICU MessageFormat, RTL, SEO, 
  performance optimization, and testing strategies.
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: internationalization
  paradigm: declarative
  capabilities:
    - next-intl-v4
    - i18next
    - react-i18next
    - vue-i18n
    - svelte-i18n
    - icu-messageformat
    - rtl-layout
    - locale-routing
    - seo-hreflang
    - translation-management
  integrates_with:
    - frontend-react
    - frontend-svelte
    - seo-optimizer
    - typescript
---

## i18n — Internationalization Mastery

### Core Philosophy

Internationalization is not translation. i18n is a **system architecture decision** that affects routing, data fetching, SEO, bundle splitting, and component design from day zero. Adding i18n after building a product costs 3-5x more than baking it in from the start.

```
┌──────────────────────────────────────────────────────────────────┐
│                     i18n ARCHITECTURE STACK                        │
│                                                                   │
│   ┌──────────────────────────────────────────────────┐           │
│   │                  APPLICATION                      │           │
│   │  ┌─────────┐ ┌──────────┐ ┌──────────────────┐  │           │
│   │  │ Routing │ │ SEO/Meta │ │   Components     │  │           │
│   │  │  /en/   │ │ hreflang │ │ t('key')         │  │           │
│   │  │  /id/   │ │ sitemap  │ │ <Trans/>         │  │           │
│   │  │  /zh/   │ │ canonical│ │ formatNumber()   │  │           │
│   │  └────┬────┘ └────┬─────┘ └────────┬─────────┘  │           │
│   │       │           │                │             │           │
│   │       ▼           ▼                ▼             │           │
│   │  ┌─────────────────────────────────────────┐     │           │
│   │  │         i18n Library Layer              │     │           │
│   │  │  next-intl | i18next | vue-i18n        │     │           │
│   │  └──────────────────┬──────────────────────┘     │           │
│   │                     │                             │           │
│   │                     ▼                             │           │
│   │  ┌─────────────────────────────────────────┐     │           │
│   │  │         Translation Files               │     │           │
│   │  │  messages/en/common.json                │     │           │
│   │  │  messages/id/landing.json               │     │           │
│   │  │  locales/zh-CN/ns1.json                │     │           │
│   │  └─────────────────────────────────────────┘     │           │
│   └──────────────────────────────────────────────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

---

### 1. i18n Architecture

#### 1.1 Translation File Structure

```
src/
├── messages/              # next-intl convention
│   ├── en/
│   │   ├── common.json        # Shared UI strings
│   │   ├── landing.json       # Landing page
│   │   ├── auth.json          # Login/register
│   │   ├── dashboard.json     # Dashboard
│   │   ├── errors.json        # Error messages
│   │   └── validation.json    # Form validation
│   ├── id/
│   │   ├── common.json
│   │   ├── landing.json
│   │   └── ...
│   ├── zh/
│   │   └── ...
│   └── ja/
│       └── ...
├── locales/               # i18next convention
│   ├── en/
│   │   ├── translation.json  # Default namespace
│   │   └── common.json
│   ├── id/
│   │   └── ...
│   └── ...
├── i18n/
│   ├── config.ts             # Shared config
│   ├── request.ts            # next-intl getRequestConfig
│   ├── routing.ts            # next-intl routing
│   └── i18next.ts            # i18next init
└── app/
    └── [locale]/             # Next.js App Router
```

#### 1.2 Namespace Strategy

```
┌──────────────────────────────────────────────────────────────┐
│                    NAMESPACE STRATEGY                          │
│                                                               │
│  Granularity:                                                  │
│    Page-level (recommended)                                    │
│    ├── common.*          → Shared UI, layout, nav             │
│    ├── landing.*         → Landing page only                  │
│    ├── auth.*            → Login/register/reset               │
│    ├── dashboard.*       → Dashboard pages                    │
│    └── errors.*          → Error boundaries, validation       │
│                                                               │
│  Why not one big file?                                        │
│  ❌ Single file → cache-busts everything on 1 key change      │
│  ❌ Single file → merge conflicts on every PR                 │
│  ❌ Single file → hard to lazy-load                           │
│  ✅ Split files → load per route, cache independently         │
│                                                               │
│  Recommendation: namespace = page/feature, NOT component      │
│  ✅ dashboard.buttons.save                                    │
│  ❌ components.button.primary.save                            │
└──────────────────────────────────────────────────────────────┘
```

#### 1.3 Fallback Chain

```typescript
// Fallback resolution order:
// 1. Exact match in target locale: messages/id/common.json → "common.greeting"
// 2. Namespace fallback: fallback NS array
// 3. Locale fallback: id → en (default locale)
// 4. Key display: "common.greeting" (missing key shown)

// next-intl default fallback config
// i18n/request.ts
import { getRequestConfig } from 'next-intl/server'

export default getRequestConfig(async ({ requestLocale }) => {
  const locale = await requestLocale

  return {
    locale,
    messages: {
      ...(await import(`../messages/${locale}/common.json`)).default,
      ...(await import(`../messages/${locale}/${locale === 'en' ? 'common' : 'landing'}.json`)).default,
    },
    timeZone: 'Asia/Jakarta',
    now: new Date(),
    fallbackLocale: 'en',
    onError: (error) => {
      if (error.code === 'MISSING_MESSAGE') {
        console.warn(`Missing i18n key: ${error.key}`)
      }
    },
  }
})
```

---

### 2. next-intl (v4)

#### 2.1 Setup — App Router

```typescript
// 1. Install
// npm install next-intl@latest

// 2. i18n/request.ts
import { getRequestConfig } from 'next-intl/server'
import { routing } from './routing'

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale
  if (!locale || !routing.locales.includes(locale as any)) {
    locale = routing.defaultLocale
  }

  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  }
})

// 3. i18n/routing.ts
import { defineRouting } from 'next-intl/routing'
import { createNavigation } from 'next-intl/navigation'

export const routing = defineRouting({
  locales: ['en', 'id', 'zh', 'ja'],
  defaultLocale: 'en',
  localePrefix: 'as-needed',  // 'always' | 'as-needed' | 'never'
  localeDetection: true,
  pathnames: {
    '/': '/',
    '/about': {
      en: '/about',
      id: '/tentang',
      zh: '/关于',
      ja: '/概要',
    },
    '/articles/[slug]': {
      en: '/articles/[slug]',
      id: '/artikel/[slug]',
      zh: '/文章/[slug]',
      ja: '/記事/[slug]',
    },
  },
})

export const { Link, redirect, usePathname, useRouter, getPathname } =
  createNavigation(routing)

// 4. middleware.ts
import createMiddleware from 'next-intl/middleware'
import { routing } from './i18n/routing'

export default createMiddleware(routing)

export const config = {
  matcher: ['/((?!api|_next|_vercel|.*\\..*).*)'],
}

// 5. layout.tsx
import { NextIntlClientProvider } from 'next-intl'
import { getMessages } from 'next-intl/server'
import { routing } from '@/i18n/routing'

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  const messages = await getMessages()

  return (
    <html lang={locale} dir={locale === 'ar' ? 'rtl' : 'ltr'}>
      <body>
        <NextIntlClientProvider locale={locale} messages={messages}>
          {children}
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
```

#### 2.2 Middleware Routing — Flow Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    LOCALE ROUTING FLOW                            │
│                                                                   │
│  Request: /id/artikel/hello-world                                 │
│                                                                   │
│  1. middleware.ts intercepts                                      │
│     ├── Matches: /(?!api|_next|.*\\..*).*                        │
│     └── createMiddleware(routing)                                 │
│                                                                   │
│  2. Extract locale from URL path                                  │
│     ├── /id/artikel/... → locale = 'id'                          │
│     ├── /en/about → locale = 'en'                                │
│     └── / → redirect to /en (default)                            │
│                                                                   │
│  3. Set cookie NEXT_LOCALE='id'                                  │
│     └── Next request without locale → check cookie               │
│                                                                   │
│  4. Rewrite URL internally                                        │
│     ├── /id/artikel/[slug] → Rewrite to /artikel/[slug]          │
│     └── App Router renders /artikel/[slug] with locale='id'     │
│                                                                   │
│  5. getRequestConfig() loads messages                             │
│     └── messages/id.json loaded, available via useTranslations() │
│                                                                   │
│  localePrefix: 'as-needed'                                        │
│  ├── Default locale (en): /about (no prefix)                     │
│  └── Other locales: /id/tentang, /zh/关于                       │
└──────────────────────────────────────────────────────────────────┘
```

#### 2.3 useTranslations — Server & Client

```typescript
// ─── Server Component ───
// app/[locale]/page.tsx
import { useTranslations } from 'next-intl'
import { getTranslations, getLocale } from 'next-intl/server'

export default async function HomePage() {
  const t = await getTranslations('landing')
  const locale = await getLocale()

  return (
    <section>
      <h1>{t('hero.title')}</h1>
      <p>{t('hero.subtitle', { appName: 'MyApp' })}</p>
      <p>
        {t.rich('hero.description', {
          bold: (chunks) => <strong>{chunks}</strong>,
          link: (chunks) => <a href="/about">{chunks}</a>,
        })}
      </p>
      <p>
        {t('hero.visitors', { count: 1234 })}
        {/* en: "1,234 visitors today" */}
        {/* id: "1.234 pengunjung hari ini" */}
      </p>
    </section>
  )
}

// ─── Client Component ───
// components/Navbar.tsx
'use client'

import { useTranslations } from 'next-intl'
import { usePathname } from '@/i18n/routing'
import LocaleSwitcher from './LocaleSwitcher'

export default function Navbar() {
  const t = useTranslations('common')
  const pathname = usePathname()

  return (
    <nav aria-label={t('nav.label')}>
      <Link href="/">{t('nav.home')}</Link>
      <Link href="/about">{t('nav.about')}</Link>
      <Link href="/articles">{t('nav.articles')}</Link>
      <LocaleSwitcher />
    </nav>
  )
}
```

#### 2.4 Formatting — Date, Number, Time

```typescript
// app/[locale]/dashboard/page.tsx
import { useTranslations } from 'next-intl'
import { getFormatter, getNow } from 'next-intl/server'

export default async function Dashboard() {
  const t = await getTranslations('dashboard')
  const format = await getFormatter()
  const now = await getNow()

  return (
    <div>
      {/* Date formatting */}
      <p>{format.dateTime(new Date('2026-05-17'), {
        dateStyle: 'full',      // Sunday, May 17, 2026
        timeStyle: 'short',     // 14:30
      })}</p>

      {/* Relative time */}
      <p>{format.relativeTime(new Date(Date.now() - 3600000))}</p>
      {/* "1 hour ago" / "1 jam yang lalu" */}

      {/* Number formatting */}
      <p>{format.number(1234567.89, {
        style: 'currency',
        currency: 'USD',
      })}</p>
      {/* en: "$1,234,567.89" | id: "USD1.234.567,89" */}

      {/* Plural-aware */}
      <p>{format.plural(3, {
        one: '# item',
        other: '# items',
      })}</p>

      {/* List formatting */}
      <p>{format.list(['Alice', 'Bob', 'Charlie'], {
        type: 'conjunction',  // "and"
      })}</p>
      {/* en: "Alice, Bob, and Charlie" */}
      {/* id: "Alice, Bob, dan Charlie" */}
    </div>
  )
}

// ─── Client-side formatting ───
'use client'

import { useFormatter } from 'next-intl'

export function DateDisplay({ date }: { date: Date }) {
  const format = useFormatter()

  return (
    <time dateTime={date.toISOString()}>
      {format.dateTime(date, {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })}
    </time>
  )
}
```

#### 2.5 Rich Text & HTML Messages

```json
{
  "welcome": "Welcome to {appName}!",
  "terms": "I agree to the <terms>Terms of Service</terms> and <privacy>Privacy Policy</privacy>.",
  "notification": "You have <b>{count}</b> new <link>messages</link>.",
  "highlight": "This is <highlight>important</highlight>."
}
```

```typescript
import { useTranslations } from 'next-intl'

export function TermsCheckbox() {
  const t = useTranslations('auth')

  return (
    <label>
      <input type="checkbox" />
      {t.rich('terms', {
        terms: (chunks) => (
          <a href="/terms" target="_blank" className="underline">
            {chunks}
          </a>
        ),
        privacy: (chunks) => (
          <a href="/privacy" target="_blank" className="underline">
            {chunks}
          </a>
        ),
      })}
    </label>
  )
}
```

#### 2.6 SEO with next-intl

```typescript
// app/[locale]/layout.tsx
import { getTranslations } from 'next-intl/server'
import { routing } from '@/i18n/routing'

type Props = {
  params: Promise<{ locale: string }>
}

export async function generateMetadata({ params }: Props) {
  const { locale } = await params
  const t = await getTranslations({ locale, namespace: 'common' })

  return {
    title: {
      template: `%s | ${t('site.name')}`,
      default: t('site.name'),
    },
    description: t('site.description'),
    keywords: t('site.keywords'),
    alternates: {
      canonical: `https://example.com/${locale}${t('site.path')}`,
      languages: Object.fromEntries(
        routing.locales.map((l) => [l, `https://example.com/${l}`])
      ),
    },
    openGraph: {
      locale: locale === 'en' ? 'en_US' : `${locale}_ID`,
      siteName: t('site.name'),
    },
  }
}

// app/[locale]/articles/[slug]/page.tsx
export async function generateMetadata({ params }: Props) {
  const { locale, slug } = await params
  const t = await getTranslations({ locale, namespace: 'articles' })

  const article = await getArticle(slug)

  return {
    title: article.title[locale],
    description: article.excerpt[locale],
    alternates: {
      canonical: `https://example.com/${locale}/articles/${slug}`,
      languages: Object.fromEntries(
        routing.locales.map((l) => [
          l,
          `https://example.com/${l}/articles/${slug}`,
        ])
      ),
    },
  }
}
```

#### 2.7 Sitemap Per Locale

```typescript
// app/sitemap.ts
import { routing } from '@/i18n/routing'
import { getPathname } from '@/i18n/routing'

const BASE_URL = 'https://example.com'

export default async function sitemap() {
  const staticPages = ['/', '/about', '/articles', '/contact']

  const entries = routing.locales.flatMap((locale) =>
    staticPages.map((page) => ({
      url: `${BASE_URL}/${locale === routing.defaultLocale ? '' : locale}${page}`,
      lastModified: new Date(),
      changeFrequency: 'monthly' as const,
      priority: page === '/' ? 1.0 : 0.8,
      alternates: {
        languages: Object.fromEntries(
          routing.locales.map((l) => [
            l,
            `${BASE_URL}/${l === routing.defaultLocale ? '' : l}${page}`,
          ])
        ),
      },
    }))
  )

  return entries
}

// ─── Dynamic sitemap with articles ───
export default async function sitemap() {
  const articles = await getAllArticles()

  const articleEntries = routing.locales.flatMap((locale) =>
    articles.map((article) => ({
      url: `${BASE_URL}/${locale}/articles/${article.slug}`,
      lastModified: article.updatedAt,
      changeFrequency: 'weekly' as const,
      priority: 0.6,
      alternates: {
        languages: Object.fromEntries(
          routing.locales.map((l) => [
            l,
            `${BASE_URL}/${l}/articles/${article.slug}`,
          ])
        ),
      },
    }))
  )

  return [...staticEntries, ...articleEntries]
}
```

---

### 3. i18next (v23+/v24+)

#### 3.1 Setup & Init

```typescript
// i18n/i18next.ts
import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import Backend from 'i18next-http-backend'

void i18next
  .use(initReactI18next)
  .use(LanguageDetector)
  .use(Backend)
  .init({
    fallbackLng: 'en',
    debug: process.env.NODE_ENV === 'development',

    // Namespace config
    ns: ['common', 'landing', 'auth', 'dashboard'],
    defaultNS: 'common',
    fallbackNS: ['common'],

    // Detection options
    detection: {
      order: ['path', 'cookie', 'localStorage', 'navigator'],
      lookupFromPathIndex: 0,
      caches: ['cookie'],
    },

    // Backend loads translation files
    backend: {
      loadPath: '/locales/{{lng}}/{{ns}}.json',
    },

    interpolation: {
      escapeValue: false,  // React already escapes
      skipOnVariables: false,
    },

    // ICU format support (optional)
    // npm install i18next-icu
    // .use(new ICU())
    // format: 'icu',

    returnObjects: false,
    returnEmptyString: false,

    parseMissingKeyHandler: (key) => {
      console.warn(`Missing i18n key: ${key}`)
      return key
    },
  })

export default i18next

// ─── Usage ───
// app/page.tsx
import { useTranslation } from 'react-i18next'

export default function Page() {
  const { t, i18n } = useTranslation('landing')

  const changeLanguage = (lng: string) => {
    void i18n.changeLanguage(lng)
  }

  return (
    <div>
      <h1>{t('hero.title')}</h1>
      <p>{t('hero.subtitle', { appName: 'MyApp' })}</p>
      <button onClick={() => changeLanguage('id')}>
        Bahasa Indonesia
      </button>
    </div>
  )
}
```

#### 3.2 Interpolation & Pluralization

```json
{
  "greeting": "Hello, {{name}}!",
  "unread": "You have {{count}} unread message",
  "unread_plural": "You have {{count}} unread messages",
  "unreadWithCount": "You have {{count}} unread {{count}} message",
  "unreadWithCount_plural": "You have {{count}} unread {{count}} messages",
  "items": "{{count}} item",
  "items_plural": "{{count}} items",
  "itemsWithCount": "{{count}} item",
  "itemsWithCount_plural": "{{count}} items"
}
```

```typescript
// i18next plural rules
t('greeting', { name: 'Alice' })
// → "Hello, Alice!"

t('unread', { count: 0 })
// en: "You have 0 unread messages"   (zero → plural)
// id: "0 pesan belum dibaca"         (id has no plural, always singular)

t('unread', { count: 1 })
// en: "You have 1 unread message"
// id: "1 pesan belum dibaca"

t('unread', { count: 5 })
// en: "You have 5 unread messages"
// id: "5 pesan belum dibaca"

// ─── ICU format (with i18next-icu) ───
// {
//   "items": "{count, plural, =0 {No items} one {# item} other {# items}}"
// }
t('items', { count: 0 })
// → "No items"
```

#### 3.3 Context & Nesting

```json
{
  "greeting": "Hello!",
  "greeting_morning": "Good morning!",
  "greeting_evening": "Good evening!",
  "gender": "{{salutation}} {{name}}",
  "gender_male": "Mr.",
  "gender_female": "Ms.",
  "nesting": "Welcome back, $t(greeting_morning)",
  "deep": {
    "nested": {
      "key": "Deep value"
    }
  }
}
```

```typescript
// Context
t('greeting', { context: 'morning' })  // → "Good morning!"
t('greeting', { context: 'evening' })  // → "Good evening!"
t('greeting')                           // → "Hello!" (fallback)

t('gender', { context: 'male', name: 'John' })
// → "Mr. John"

t('gender', { context: 'female', name: 'Jane' })
// → "Ms. Jane"

// Nesting with $t()
t('nesting')
// → "Welcome back, Good morning!"

// Deep keys using dot notation
t('deep.nested.key')
// → "Deep value"

// ─── Format function ───
// Custom format function in init
{
  interpolation: {
    format: (value, format, lng) => {
      if (format === 'uppercase') return value.toUpperCase()
      if (format === 'lowercase') return value.toLowerCase()
      if (format === 'capitalize') {
        return value.charAt(0).toUpperCase() + value.slice(1)
      }
      if (format === 'date') {
        return new Intl.DateTimeFormat(lng).format(value)
      }
      return value
    },
  },
}

// Usage in translation
// { "uploaded": "Uploaded {{date, date}}" }
t('uploaded', { date: new Date() })
// → "Uploaded 5/17/2026" (US)
// → "Uploaded 17/5/2026" (ID)
```

#### 3.4 Lazy Loading

```typescript
// i18n/i18next.ts
import i18next from 'i18next'
import Backend from 'i18next-http-backend'

void i18next
  .use(Backend)
  .init({
    ns: ['common'],
    defaultNS: 'common',
    fallbackLng: 'en',
    partialBundledLanguages: true,

    backend: {
      // Translations loaded on demand
      loadPath: '/locales/{{lng}}/{{ns}}.json',
      request: (options, url, payload, callback) => {
        try {
          fetch(url)
            .then((res) => res.json())
            .then((data) => callback(null, { status: 200, data }))
            .catch((err) => callback(err, { status: 404 }))
        } catch (err) {
          callback(err as Error, { status: 500 })
        }
      },
    },
  })

// ─── Load namespace on demand ───
async function loadDashboardTranslations() {
  await i18next.loadNamespaces('dashboard')
}

// ─── Preload critical namespaces ───
void i18next.loadNamespaces(['common', 'landing'])
```

---

### 4. react-i18next

#### 4.1 useTranslation Hook

```typescript
// components/UserProfile.tsx
import { useTranslation } from 'react-i18next'

interface UserProfileProps {
  user: {
    name: string
    role: 'admin' | 'user' | 'moderator'
    unreadCount: number
  }
}

export function UserProfile({ user }: UserProfileProps) {
  const { t, i18n } = useTranslation(['common', 'dashboard'])
  const currentLang = i18n.language

  return (
    <div>
      <h2>{t('common:profile.title')}</h2>
      <p>{t('dashboard:welcome', { name: user.name })}</p>
      <p>{t('common:role', { context: user.role })}</p>
      <p>{t('common:unread', { count: user.unreadCount })}</p>

      {/* Access namespace explicitly with prefix */}
      <p>{t('common:notifications.empty')}</p>
      <p>{t('dashboard:stats.visitors')}</p>

      {/* Current language */}
      <p>{t('common:currentLang', { lang: currentLang })}</p>
    </div>
  )
}
```

#### 4.2 Trans Component

```typescript
import { Trans } from 'react-i18next'

// messages: {
//   "intro": "Welcome to <1>MyApp</1> — the best platform for <2>building products</2>.",
//   "terms": "By continuing, you agree to our <link>Terms of Service</link>.",
//   "notification": "<0>{{name}}</0> sent you a <1>friend request</1>."
// }

export function WelcomeBanner() {
  return (
    <div>
      <Trans i18nKey="intro" ns="landing">
        {/* Index-based component mapping */}
        Welcome to <strong>MyApp</strong> — the best platform for{' '}
        <em>building products</em>.
      </Trans>
    </div>
  )
}

export function TermsNotice() {
  return (
    <Trans i18nKey="terms" ns="auth">
      By continuing, you agree to our{' '}
      <a href="/terms" target="_blank">
        Terms of Service
      </a>
      .
    </Trans>
  )
}

// ─── Trans with components prop ───
export function Notification({ name }: { name: string }) {
  return (
    <Trans
      i18nKey="notification"
      ns="common"
      values={{ name }}
      components={[
        <strong key="name" className="font-semibold" />,
        <button key="link" className="text-blue-500 hover:underline" />,
      ]}
    />
  )
}
```

#### 4.3 withTranslation HOC

```typescript
import { withTranslation, WithTranslation } from 'react-i18next'

interface FooterProps extends WithTranslation {
  year: number
}

class Footer extends React.Component<FooterProps> {
  render() {
    const { t, year } = this.props

    return (
      <footer>
        <p>&copy; {year} {t('common:footer.copyright')}</p>
        <nav>
          <a href="/privacy">{t('common:footer.privacy')}</a>
          <a href="/terms">{t('common:footer.terms')}</a>
        </nav>
      </footer>
    )
  }
}

export default withTranslation(['common'])(Footer)
```

#### 4.4 useSSR & Suspense

```typescript
import { useTranslation } from 'react-i18next'
import { Suspense } from 'react'

// ─── SSR-safe usage ───
export function SSRPage() {
  const { t, ready } = useTranslation('landing', { useSuspense: false })

  if (!ready) {
    return <LoadingSkeleton />
  }

  return <h1>{t('hero.title')}</h1>
}

// ─── With Suspense ───
function DashboardContent() {
  const { t } = useTranslation('dashboard')
  return <div>{t('welcome')}</div>
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div>Loading translations...</div>}>
      <DashboardContent />
    </Suspense>
  )
}
```

---

### 5. Translation Management

#### 5.1 Key Naming Conventions

```
┌──────────────────────────────────────────────────────────────┐
│                   KEY NAMING CONVENTIONS                       │
│                                                               │
│  Format: [namespace].[section].[descriptor].[modifier]        │
│                                                               │
│  ✅ Good examples:                                            │
│  common.nav.home                                              │
│  common.nav.about                                             │
│  landing.hero.title                                           │
│  landing.hero.subtitle                                        │
│  landing.hero.cta                                             │
│  auth.login.title                                             │
│  auth.login.emailLabel                                        │
│  auth.login.passwordLabel                                     │
│  auth.login.submit                                            │
│  dashboard.stats.visitors.label                               │
│  dashboard.stats.visitors.value                               │
│  errors.validation.email.required                             │
│  errors.validation.email.invalid                              │
│  errors.not_found.title                                       │
│                                                               │
│  ❌ Bad examples:                                             │
│  title                        → too vague                     │
│  landing.hero.button.label    → too deep, redundant           │
│  btn-submit                   → tied to component, not page   │
│  HomePageTitle                → PascalCase, not portable      │
│  common_home_nav              → underscores, inconsistent     │
│  t('login.0')                 → array indices, unreadable     │
│                                                               │
│  Rules:                                                       │
│  1. All lowercase with dots                                   │
│  2. Max 4 segments                                            │
│  3. Namespace = page/feature (not component)                  │
│  4. Semantic, not visual (❌ 'button.red', ✅ 'actions.delete')│
│  5. Consistent across all locales                             │
└──────────────────────────────────────────────────────────────┘
```

#### 5.2 Naming Strategy

```typescript
// ─── Translation file: messages/en/auth.json ───
{
  "login": {
    "title": "Sign In",
    "subtitle": "Welcome back",
    "emailLabel": "Email address",
    "passwordLabel": "Password",
    "rememberMe": "Remember me",
    "forgotPassword": "Forgot password?",
    "submit": "Sign in",
    "loading": "Signing in...",
    "success": "Welcome back, {name}!",
    "error": {
      "invalid": "Invalid email or password",
      "locked": "Account locked. Try again in {minutes} minutes",
      "tooManyAttempts": "Too many attempts. Please try again later"
    },
    "divider": "or continue with",
    "social": {
      "google": "Google",
      "github": "GitHub"
    },
    "noAccount": "Don't have an account?",
    "signupLink": "Create one"
  },
  "register": {
    "title": "Create Account",
    "nameLabel": "Full name",
    "confirmPassword": "Confirm password",
    "agreeTerms": "I agree to the Terms of Service",
    "submit": "Create account",
    "hasAccount": "Already have an account?",
    "loginLink": "Sign in"
  }
}
```

#### 5.3 File Organization

```typescript
// ─── Script: scripts/sync-translations.ts ───
// Auto-detect missing keys and add them to all locale files
import * as fs from 'fs/promises'
import * as path from 'path'

const LOCALES_DIR = path.resolve('messages')
const LOCALES = ['en', 'id', 'zh', 'ja']
const NAMESPACES = ['common', 'landing', 'auth', 'dashboard', 'errors', 'validation']

async function syncTranslations() {
  const referenceKeys = await extractKeys('en')

  for (const locale of LOCALES) {
    if (locale === 'en') continue

    for (const ns of NAMESPACES) {
      const filePath = path.join(LOCALES_DIR, locale, `${ns}.json`)
      const existing = JSON.parse(await fs.readFile(filePath, 'utf-8'))
      const reference = JSON.parse(
        await fs.readFile(path.join(LOCALES_DIR, 'en', `${ns}.json`), 'utf-8')
      )

      const missingKeys = findMissingKeys(reference, existing)

      if (missingKeys.length > 0) {
        console.warn(`[${locale}/${ns}] Missing keys:`, missingKeys)
        // Add placeholder keys
        const enriched = addMissingKeys(existing, reference, missingKeys)
        await fs.writeFile(filePath, JSON.stringify(enriched, null, 2))
      }
    }
  }
}
```

---

### 6. ICU MessageFormat

#### 6.1 Format Reference

```
┌──────────────────────────────────────────────────────────────┐
│                  ICU MESSAGEFORMAT REFERENCE                    │
│                                                               │
│  {var}                          → Simple variable             │
│  {var, plural, ...}             → Plural selection            │
│  {var, select, ...}             → Select (gender, etc.)      │
│  {var, selectordinal, ...}      → Ordinal (1st, 2nd, 3rd)    │
│  {var, date, ::yyyyMMdd}       → Date formatting             │
│  {var, number, ::currency/USD} → Number/currency             │
│  {var, time, ::short}          → Time formatting             │
│                                                               │
│  #  → The plural/ordinal value (digits formatted localely)    │
│  offset:N → Offset value before plural matching               │
└──────────────────────────────────────────────────────────────┘
```

#### 6.2 Plural Rules

```json
{
  "items": "{count, plural, =0 {No items} one {# item} other {# items}}",
  "photos": "{count, plural, =0 {No photos} one {# photo} other {# photos}}",
  "guests": "{count, plural, offset:1 =0 {Nobody} =1 {Just you} one {You and # other} other {You and # others}}"
}
```

```typescript
// ICU plural forms per locale
//
// English (en):
//   singular: 1 → "1 item"
//   plural:   0, 2, 3, ... → "0 items", "2 items"
//
// Indonesian (id): NO plural forms
//   all → "1 item", "5 item"
//   Use count context instead:
//   { "items": "{count, plural, =0 {Tidak ada} other {# item}}"}
//   → "Tidak ada", "1 item", "5 item"
//
// Arabic (ar): SIX forms
//   zero, one, two, few, many, other
//
// Russian (ru): FOUR forms
//   one, few, many, other
//
// Japanese (ja), Chinese (zh), Korean (ko): NO plurals
//   Use {count}items or explicit count word
//
// Polish (pl): FOUR forms
//   one, few, many, other

// ─── next-intl usage ───
import { useTranslations } from 'next-intl'

function ItemList({ count }: { count: number }) {
  const t = useTranslations('common')

  return (
    <p>
      {t('items', { count })}
      {/* en (1): "1 item" | en (5): "5 items" */}
      {/* id (1): "1 item" | id (5): "5 item" (no plural) */}
      {/* pl (1): "1 element" | pl (2): "2 elementy" | pl (5): "5 elementów" */}
    </p>
  )
}
```

#### 6.3 Select & Ordinal

```json
{
  "gender": "{gender, select, male {He has} female {She has} other {They have}} joined the team.",
  "pronoun": "{gender, select, male {his} female {her} other {their}} profile",
  "ordinalExample": "You finished {place, selectordinal, one {#st} two {#nd} few {#rd} other {#th}}!",
  "nested": "{count, plural, one {{gender, select, male {He} female {She} other {They}} submitted # file} other {{gender, select, male {He} female {She} other {They}} submitted # files}}"
}
```

```typescript
// Select
t('gender', { gender: 'male' })
// → "He has joined the team."

t('pronoun', { gender: 'female' })
// → "her profile"

// Ordinal
t('ordinalExample', { place: 1 })
// → "You finished 1st!"

t('ordinalExample', { place: 3 })
// → "You finished 3rd!"

t('ordinalExample', { place: 5 })
// → "You finished 5th!"

// Nested select + plural
t('nested', { count: 1, gender: 'female' })
// → "She submitted 1 file"

t('nested', { count: 3, gender: 'male' })
// → "He submitted 3 files"
```

#### 6.4 Date/Number in ICU

```json
{
  "published": "Published on {date, date, long}",
  "price": "Price: {amount, number, ::currency/USD}",
  "updated": "Last updated {date, date, ::yyyyMMdd} at {time, time, ::short}",
  "percentage": "Progress: {value, number, ::percent}",
  "compact": "Views: {count, number, ::compact-short}"
}
```

```typescript
t('published', { date: new Date('2026-05-17') })
// en: "Published on May 17, 2026"
// id: "Dipublikasikan pada 17 Mei 2026"

t('price', { amount: 1234.56 })
// en: "Price: $1,234.56"
// id: "Price: USD1.234,56"

t('percentage', { value: 0.75 })
// en: "Progress: 75%"
// id: "Progress: 75%"

t('compact', { count: 1234567 })
// en: "Views: 1.2M"
// id: "Views: 1,2 jt"
```

---

### 7. SEO & i18n

#### 7.1 hreflang Implementation

```typescript
// Generate hreflang tags per page
// app/[locale]/layout.tsx
export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params

  return {
    alternates: {
      canonical: `https://example.com/${locale}`,
      languages: {
        'en': 'https://example.com/en',
        'id': 'https://example.com/id',
        'zh': 'https://example.com/zh',
        'ja': 'https://example.com/ja',
        'x-default': 'https://example.com/en',  // Default (usually English)
      },
    },
  }
}

// ─── Generated HTML ───
// <link rel="alternate" hreflang="en" href="https://example.com/en" />
// <link rel="alternate" hreflang="id" href="https://example.com/id" />
// <link rel="alternate" hreflang="zh" href="https://example.com/zh" />
// <link rel="alternate" hreflang="ja" href="https://example.com/ja" />
// <link rel="alternate" hreflang="x-default" href="https://example.com/en" />
// <link rel="canonical" href="https://example.com/en/about" />
```

#### 7.2 Localized URLs

```typescript
// i18n/routing.ts — pathname mapping
export const routing = defineRouting({
  locales: ['en', 'id', 'zh', 'ja'],
  defaultLocale: 'en',
  pathnames: {
    '/': '/',
    '/about': {
      en: '/about',
      id: '/tentang-kami',
      zh: '/关于我们',
      ja: '/私たちについて',
    },
    '/services': {
      en: '/services',
      id: '/layanan',
      zh: '/服务',
      ja: '/サービス',
    },
    '/articles/[slug]': {
      en: '/articles/[slug]',
      id: '/artikel/[slug]',
      zh: '/文章/[slug]',
      ja: '/記事/[slug]',
    },
    '/categories/[category]/[page]': {
      en: '/categories/[category]/[page]',
      id: '/kategori/[category]/[page]',
      zh: '/分类/[category]/[page]',
      ja: '/カテゴリ/[category]/[page]',
    },
  },
})

// ─── Usage ───
// In component:
<Link href={{ pathname: '/about' }}>
  About
</Link>
// en → /about
// id → /tentang-kami
// zh → /关于我们
```

#### 7.3 Localized Meta Tags

```typescript
// app/[locale]/articles/[slug]/page.tsx
import { getTranslations } from 'next-intl/server'

interface ArticlePageProps {
  params: Promise<{ locale: string; slug: string }>
}

export async function generateMetadata({ params }: ArticlePageProps) {
  const { locale, slug } = await params
  const t = await getTranslations({ locale, namespace: 'articles' })
  const article = await getArticleBySlug(slug)

  return {
    title: `${article.title} | ${t('siteName')}`,
    description: article.excerpt,
    keywords: article.tags.join(', '),
    openGraph: {
      title: article.title,
      description: article.excerpt,
      type: 'article',
      publishedTime: article.publishedAt,
      authors: [article.author],
      images: [{ url: article.ogImage }],
      locale: locale === 'en' ? 'en_US' : `${locale}_${locale.toUpperCase()}`,
    },
    twitter: {
      card: 'summary_large_image',
      title: article.title,
      description: article.excerpt,
      images: [article.ogImage],
    },
    alternates: {
      canonical: `https://example.com/${locale}/articles/${slug}`,
      languages: Object.fromEntries(
        routing.locales.map((l) => [
          l,
          `https://example.com/${l}/articles/${article.slugMap[l] || slug}`,
        ])
      ),
    },
    robots: {
      index: true,
      follow: true,
      'max-image-preview': 'large',
    },
  } satisfies Metadata
}
```

#### 7.4 Localized JSON-LD

```typescript
// app/[locale]/articles/[slug]/ArticleJsonLd.tsx
import { routing } from '@/i18n/routing'

export function ArticleJsonLd({
  article,
  locale,
}: {
  article: {
    title: string
    excerpt: string
    publishedAt: string
    author: string
    image: string
  }
  locale: string
}) {
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': 'Article',
    headline: article.title,
    description: article.excerpt,
    datePublished: article.publishedAt,
    author: {
      '@type': 'Person',
      name: article.author,
    },
    image: article.image,
    inLanguage: locale,
    isPartOf: {
      '@type': 'WebSite',
      name: 'Example',
      inLanguage: routing.locales,
    },
    mainEntityOfPage: {
      '@type': 'WebPage',
      '@id': `https://example.com/${locale}/articles/${article.slug}`,
    },
  }

  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
    />
  )
}
```

---

### 8. Performance

#### 8.1 Lazy Loading Translations

```typescript
// ─── next-intl: Tree-shake per page ───
// i18n/request.ts
export default getRequestConfig(async ({ requestLocale }) => {
  const locale = await requestLocale

  // Only load messages for current locale
  // Webpack/Rsbuild will split chunks per locale
  return {
    locale,
    messages: (await import(`../messages/${locale}.json`)).default,
  }
})

// ─── Manual chunking with namespace ───
// app/[locale]/dashboard/page.tsx
import { getTranslations } from 'next-intl/server'
import { unstable_setRequestLocale } from 'next-intl/server'

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  unstable_setRequestLocale(locale)

  // Only loads dashboard namespace
  const t = await getTranslations('dashboard')

  return <h1>{t('title')}</h1>
}
```

#### 8.2 Caching Strategy

```typescript
// ─── next-intl: Built-in caching ───
// Messages are cached at the request level automatically
// Additional caching with React cache()
import { cache } from 'react'
import { getMessages } from 'next-intl/server'

export const getCachedMessages = cache(async (locale: string) => {
  return (await import(`../messages/${locale}.json`)).default
})

// ─── i18next: Cache translations in memory ───
// i18next caches loaded resources by default
// To preload critical languages:
await i18next.loadResources('en', ['common', 'landing'])
await i18next.loadResources('id', ['common', 'landing'])

// ─── localStorage caching (i18next) ───
import i18next from 'i18next'
import Backend from 'i18next-http-backend'
import { cache } from 'i18next-localstorage-cache'

void i18next
  .use(Backend)
  .use(cache)
  .init({
    cache: {
      enabled: true,
      prefix: 'i18n_cache_',
      expirationTime: 24 * 60 * 60 * 1000,  // 24 hours
    },
  })
```

#### 8.3 Bundle Size Optimization

```typescript
// ─── Dynamic import per locale ───
// Instead of importing all locales at once:
// ❌ Bad:
import en from '../locales/en.json'
import id from '../locales/id.json'
// → Both languages in every bundle

// ✅ Good (next-intl):
// Only imports the current locale at request time
// Webpack code splitting per locale

// ✅ Good (i18next + dynamic import):
const loadLocale = async (locale: string) => {
  const resources = await import(`../locales/${locale}.json`)
  i18next.addResourceBundle(locale, 'translation', resources)
}

// ─── Tree-shake ICU ───
// If you don't need ICU format, don't import i18next-icu
// ICU adds ~8KB to bundle

// ─── Minimal i18next config for production ───
void i18next.init({
  // ❌ Remove in production:
  // debug: true,
  // returnObjects: true,
  // parseMissingKeyHandler: ... (only in dev)

  // ✅ Production-only:
  debug: false,
  cleanCode: true,
})
```

---

### 9. RTL — Right-to-Left Layout

#### 9.1 Tailwind RTL Variants

```typescript
// ─── Tailwind RTL support (Tailwind v3.4+) ───
// tailwind.config.ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./src/**/*.{ts,tsx}'],
  future: {
    hoverOnlyWhenSupported: true,
  },
} satisfies Config

// ─── RTL utility classes ───
// `ltr:` prefix — applies only in LTR mode
// `rtl:` prefix — applies only in RTL mode

{/* Text alignment */}
<p className="text-left rtl:text-right">
  {t('welcome')}
</p>

{/* Margins for icon/text ordering */}
<button>
  <span className="mr-2 rtl:mr-0 rtl:ml-2">
    → {/* Arrow icon */}
  </span>
  {t('next')}
</button>

{/* Flex direction */}
<div className="flex rtl:flex-row-reverse">
  <Sidebar />
  <MainContent />
</div>

{/* Border radius */}
<div className="rounded-l-lg rtl:rounded-l-none rtl:rounded-r-lg">
  {t('content')}
</div>

{/* Translating abstract spacing */}
{/* Use logical properties when possible: */}
<div className="ltr:pl-4 rtl:pr-4">
  {t('sidebar.title')}
</div>
```

#### 9.2 CSS Logical Properties

```css
/* ✅ Preferred: CSS logical properties (no LTR/RTL class switching) */
.element {
  padding-inline-start: 1rem;    /* left in LTR, right in RTL */
  padding-inline-end: 1rem;      /* right in LTR, left in RTL */
  margin-inline: auto;
  border-inline-start: 2px solid;
  text-align: start;             /* left in LTR, right in RTL */
  inset-inline-start: 0;        /* left in LTR, right in RTL */
}

/* ❌ Avoid: Physical properties in RTL-aware components */
.bad {
  margin-left: 1rem;
  padding-right: 1rem;
  border-left: 2px solid;
  text-align: left;
}
```

#### 9.3 RTL-Aware Components

```typescript
// components/Pagination.tsx
interface PaginationProps {
  currentPage: number
  totalPages: number
  dir: 'ltr' | 'rtl'
}

export function Pagination({ currentPage, totalPages, dir }: PaginationProps) {
  const isRTL = dir === 'rtl'
  const PrevIcon = isRTL ? ChevronRight : ChevronLeft
  const NextIcon = isRTL ? ChevronLeft : ChevronRight

  return (
    <nav aria-label="Pagination">
      <button disabled={currentPage <= 1}>
        <PrevIcon className="w-4 h-4" />
      </button>
      <span>{currentPage} of {totalPages}</span>
      <button disabled={currentPage >= totalPages}>
        <NextIcon className="w-4 h-4" />
      </button>
    </nav>
  )
}

// ─── Locale-aware direction ───
const RTL_LOCALES = new Set(['ar', 'he', 'fa', 'ur', 'ps', 'ku'])

export function getDir(locale: string): 'ltr' | 'rtl' {
  return RTL_LOCALES.has(locale) ? 'rtl' : 'ltr'
}

// ─── Usage in layout ───
export default function RootLayout({ children, params }: {
  children: React.ReactNode
  params: { locale: string }
}) {
  const dir = getDir(params.locale)

  return (
    <html lang={params.locale} dir={dir}>
      <body className={dir === 'rtl' ? 'rtl-mode' : 'ltr-mode'}>
        {children}
      </body>
    </html>
  )
}
```

#### 9.4 RTL Icons & SVGs

```typescript
// ─── Flip icons in RTL ───
// components/Icon.tsx
interface IconProps {
  name: 'arrow-left' | 'arrow-right' | 'chevron-left' | 'chevron-right'
  dir: 'ltr' | 'rtl'
  className?: string
}

const FLIP_ICONS = new Set([
  'arrow-left',
  'arrow-right',
  'chevron-left',
  'chevron-right',
])

export function Icon({ name, dir, className }: IconProps) {
  const shouldFlip = FLIP_ICONS.has(name) && dir === 'rtl'

  return (
    <svg
      className={cn(className, shouldFlip && 'scale-x-[-1]')}
      /* ... SVG paths */
    >
      {/* SVG content */}
    </svg>
  )
}

// ─── Or use a RTL-aware icon mapping ───
const ICON_MAP = {
  'ltr': {
    'arrow-left': '←',
    'arrow-right': '→',
    'chevron-left': '‹',
    'chevron-right': '›',
  },
  'rtl': {
    'arrow-left': '→',
    'arrow-right': '←',
    'chevron-left': '›',
    'chevron-right': '‹',
  },
}
```

---

### 10. Testing i18n

#### 10.1 Mocking Translation Hooks

```typescript
// ─── Jest/Vitest: Mock useTranslations (next-intl) ───
// __mocks__/next-intl.ts
const mockTranslations = new Proxy(
  (key: string, params?: Record<string, any>) => {
    if (params) {
      return Object.entries(params).reduce(
        (str, [k, v]) => str.replace(`{${k}}`, String(v)),
        key
      )
    }
    return key
  },
  {
    get: (_, prop: string) => {
      if (prop === 'rich') {
        return (key: string, components: Record<string, any>) => key
      }
      return mockTranslations
    },
  }
)

export const useTranslations = () => mockTranslations

export const getTranslations = async () => mockTranslations

// ─── Test example ───
// components/__tests__/Navbar.test.tsx
import { render, screen } from '@testing-library/react'
import Navbar from '../Navbar'

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string) => key,
}))

vi.mock('@/i18n/routing', () => ({
  Link: ({ children, href }: any) => <a href={href}>{children}</a>,
  usePathname: () => '/',
}))

describe('Navbar', () => {
  it('renders nav links with translation keys', () => {
    render(<Navbar />)
    expect(screen.getByText('common.nav.home')).toBeInTheDocument()
    expect(screen.getByText('common.nav.about')).toBeInTheDocument()
  })
})
```

#### 10.2 Mocking i18next

```typescript
// ─── Vitest setup for i18next ───
// vitest.setup.ts
import i18next from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from '../locales/en/translation.json'

void i18next.use(initReactI18next).init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['translation'],
  defaultNS: 'translation',
  resources: {
    en: { translation: en },
  },
  interpolation: { escapeValue: false },
})

// ─── Alternative: Simple mock ───
// __mocks__/react-i18next.ts
export const useTranslation = () => ({
  t: (key: string, params?: Record<string, any>) => {
    if (params) {
      return Object.entries(params).reduce(
        (str, [k, v]) => str.replace(`{{${k}}}`, String(v)),
        key
      )
    }
    return key
  },
  i18n: {
    language: 'en',
    changeLanguage: vi.fn(),
  },
  ready: true,
})
```

#### 10.3 Snapshot Testing with Locale

```typescript
// components/__tests__/WelcomeBanner.test.tsx
import { render } from '@testing-library/react'
import WelcomeBanner from '../WelcomeBanner'

const locales = ['en', 'id', 'zh', 'ja'] as const

describe('WelcomeBanner snapshots', () => {
  it.each(locales)('renders correctly in %s', (locale) => {
    vi.mock('next-intl/server', () => ({
      getTranslations: async () => (key: string, params?: any) => {
        // Return locale-aware mock
        return `${key}_${locale}`
      },
      getLocale: async () => locale,
    }))

    const { container } = render(<WelcomeBanner />)
    expect(container).toMatchSnapshot(`WelcomeBanner-${locale}`)
  })
})

// ─── Testing format functions ───
// utils/__tests__/format.test.ts
import { useFormatter } from 'next-intl'

describe('format.dateTime', () => {
  it('formats date correctly for en locale', () => {
    vi.mock('next-intl', () => ({
      useFormatter: () => ({
        dateTime: vi.fn((date: Date, options?: any) => {
          return new Intl.DateTimeFormat('en', options).format(date)
        }),
      }),
    }))

    const format = useFormatter()
    const result = format.dateTime(new Date('2026-05-17'), {
      dateStyle: 'full',
    })
    expect(result).toBe('Sunday, May 17, 2026')
  })
})
```

#### 10.4 Testing Locale Switching

```typescript
// components/__tests__/LocaleSwitcher.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import LocaleSwitcher from '../LocaleSwitcher'

const mockRouter = { push: vi.fn(), replace: vi.fn() }
const mockPathname = '/'

vi.mock('@/i18n/routing', () => ({
  usePathname: () => mockPathname,
  useRouter: () => mockRouter,
  routing: {
    locales: ['en', 'id', 'zh', 'ja'],
    defaultLocale: 'en',
  },
}))

describe('LocaleSwitcher', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders all locale options', () => {
    render(<LocaleSwitcher />)
    expect(screen.getByText('English')).toBeInTheDocument()
    expect(screen.getByText('Bahasa Indonesia')).toBeInTheDocument()
    expect(screen.getByText('中文')).toBeInTheDocument()
    expect(screen.getByText('日本語')).toBeInTheDocument()
  })

  it('navigates on locale change', () => {
    render(<LocaleSwitcher />)
    fireEvent.click(screen.getByText('Bahasa Indonesia'))
    expect(mockRouter.replace).toHaveBeenCalledWith('/')
  })
})
```

---

### 11. File Convention

```
┌──────────────────────────────────────────────────────────────┐
│              TRANSLATION FILE CONVENTION                       │
│                                                               │
│  next-intl project:                                           │
│                                                               │
│  messages/                                                    │
│  ├── en/                                                      │
│  │   ├── common.json                    → Shared strings      │
│  │   ├── landing.json                   → Landing page        │
│  │   ├── auth.json                      → Auth pages          │
│  │   ├── dashboard.json                 → Dashboard pages     │
│  │   ├── errors.json                    → Error messages      │
│  │   ├── validation.json                → Form validation     │
│  │   ├── blog.json                      → Blog pages          │
│  │   └── email.json                     → Email templates     │
│  ├── id/                                                      │
│  │   └── (same structure as en/)                              │
│  ├── zh/                                                      │
│  │   └── (same structure as en/)                              │
│  └── index.json                        → Collation file      │
│                                                               │
│  i18next project:                                             │
│                                                               │
│  locales/                                                     │
│  ├── en/                                                      │
│  │   ├── translation.json              → Default namespace    │
│  │   └── common.json                   → Common namespace     │
│  ├── id/                                                      │
│  │   └── (same structure)                                     │
│  └── dev/                                                     │
│       └── translation.json            → Dev-only overrides   │
│                                                               │
│  Naming rules:                                                │
│  ├── kebab-case.json (always)                                 │
│  ├── 1 namespace = 1 file                                     │
│  ├── Max 200 lines per file                                   │
│  ├── Max 3 levels of nesting                                  │
│  └── Key order: alphabetical for git diff readability         │
│                                                               │
│  Tooling:                                                     │
│  ├── i18n-ally (VS Code) — inline preview                    │
│  ├── i18next-parser — extract keys from code                 │
│  └── formatjs (ICU) — lint + compile ICU messages            │
└──────────────────────────────────────────────────────────────┘
```

#### 11.1 VS Code i18n-ally Settings

```json
{
  "i18n-ally.localesPaths": ["messages"],
  "i18n-ally.sourceLanguage": "en",
  "i18n-ally.displayLanguage": "en",
  "i18n-ally.keystyle": "nested",
  "i18n-ally.sortKeys": true,
  "i18n-ally.enabledFrameworks": ["next-intl"],
  "i18n-ally.translateSpeed": 3,
  "i18n-ally.autoTranslate": false,
  "i18n-ally.preferredTranslationEngine": "google"
}
```

---

### 12. Anti-Patterns

#### 12.1 Inline Strings

```typescript
// ❌ ANTI-PATTERN: Hardcoded strings
function Header() {
  return (
    <header>
      <h1>Welcome to MyApp</h1>
      <nav>
        <a href="/">Home</a>
        <a href="/about">About Us</a>
      </nav>
    </header>
  )
}

// ✅ CORRECT: Use translation keys
function Header() {
  const t = useTranslations('common')

  return (
    <header>
      <h1>{t('site.title')}</h1>
      <nav>
        <Link href="/">{t('nav.home')}</Link>
        <Link href="/about">{t('nav.about')}</Link>
      </nav>
    </header>
  )
}
```

#### 12.2 Missing Keys

```typescript
// ❌ ANTI-PATTERN: Silent missing keys
// next-intl config:
// onError: undefined  ← Default: silently returns key name
// → No warning in development, broken UI in production

// ✅ CORRECT: Configure error handling
export default getRequestConfig(async () => ({
  onError: (error) => {
    if (error.code === 'MISSING_MESSAGE') {
      // Log to monitoring
      console.error(`Missing translation: ${error.key}`)
      // Could also send to Sentry
    }
  },
  getMessageFallback: ({ key, namespace }) => {
    // Return a visible fallback in development
    if (process.env.NODE_ENV === 'development') {
      return `🔤 ${key}`
    }
    return key
  },
}))
```

#### 12.3 Mixing Locales

```typescript
// ❌ ANTI-PATTERN: Mixed locale data
function ArticleCard({ article }: { article: Article }) {
  return (
    <div>
      <h2>{article.title}</h2>
      {/* ❌ If article.title is a single string, it's in one locale only */}
      {/* ✅ article should contain all locales: */}
      {/* { en: "Hello", id: "Halo" } */}
    </div>
  )
}

// ✅ CORRECT: Store data per locale
interface Article {
  id: string
  slug: string
  title: {
    en: string
    id: string
    zh: string
    ja: string
  }
  content: {
    en: string
    id: string
    zh: string
    ja: string
  }
}

function ArticleCard({ article, locale }: { article: Article; locale: string }) {
  const t = useTranslations('articles')

  return (
    <div>
      <h2>{article.title[locale as keyof typeof article.title]}</h2>
      <p>{t('readMore')}</p>
    </div>
  )
}
```

#### 12.4 Broken Interpolation

```typescript
// ❌ ANTI-PATTERN: Missing interpolation values
function Greeting({ name }: { name?: string }) {
  const t = useTranslations('common')
  return <p>{t('greeting', { name })}</p>
  // If name is undefined → "Hello, undefined!"
  // If name is null → "Hello, null!"
}

// ✅ CORRECT: Handle missing values
function Greeting({ name }: { name?: string }) {
  const t = useTranslations('common')
  return <p>{t('greeting', { name: name ?? t('guest') })}</p>
}

// ❌ ANTI-PATTERN: Passing React elements as interpolation values
t('welcome', { link: <a href="/">here</a> })
// i18next: [Object object] — React elements cannot be serialized

// ✅ Use Trans component or rich text instead
t.rich('welcome', { link: (chunks) => <a href="/">{chunks}</a> })
// or
<Trans i18nKey="welcome" components={{ link: <a href="/" /> }} />
```

#### 12.5 Other Anti-Patterns

```typescript
// ❌ ANTI-PATTERN: Deep nesting (>3 levels)
// "a.b.c.d.e": "too deep" — hard to maintain, hard to read

// ❌ ANTI-PATTERN: Reusing keys across contexts
// "submit": "Save"      ← Reused for both login and settings
// → Can't translate differently per context

// ❌ ANTI-PATTERN: HTML in translation strings
// "text": "Click <a href='/x'>here</a>"
// → Use rich text or Trans instead

// ❌ ANTI-PATTERN: Numeric or non-descriptive keys
// "0": "Home", "1": "About"  ← Can't understand without context
// "err_001": "Not found"      ← Opaque

// ❌ ANTI-PATTERN: Conditionally rendering translation hooks
function Bad({ condition }: { condition: boolean }) {
  const t = useTranslations('common')
  const t2 = useTranslations('dashboard')
  const activeT = condition ? t : t2  // ❌ Hooks called conditionally
  return <p>{activeT('title')}</p>
}

// ✅ Use namespace prefix with a single hook
function Good({ condition }: { condition: boolean }) {
  const t = useTranslations(condition ? 'common' : 'dashboard')
  // ✅ OK — namespace changes but hook is stable
  return <p>{t('title')}</p>
}

// ❌ ANTI-PATTERN: Concatenating translated strings
// t('hello') + ' ' + t('world') + '!'
// → Cannot reorder for different languages
// ✅ Use message formatting:
// t('greeting', { name: t('world') })
// { "greeting": "Hello {name}!" }

// ❌ ANTI-PATTERN: Gender via string replacement
// t('he_joined').replace('{gender}', gender === 'male' ? 'He' : 'She')
// → Use ICU select format instead

// ❌ ANTI-PATTERN: Storing translations outside locale files
// const translations = { en: { hello: "Hello" } }
// → Cannot be extracted by i18n tools, no key analysis
```

---

### 13. Implementation Checklist

```
┌──────────────────────────────────────────────────────────────┐
│                  i18n IMPLEMENTATION CHECKLIST                 │
│                                                               │
│  [ ] 1. Architecture Decision                                 │
│       ├── Choose library: next-intl / i18next / vue-i18n     │
│       ├── Decide: path-based vs cookie vs domain locale       │
│       └── Choose namespace strategy                           │
│                                                               │
│  [ ] 2. Project Setup                                         │
│       ├── Install dependencies                                │
│       ├── Create message file structure                       │
│       ├── Configure i18n middleware (Next.js)                 │
│       └── Set up locale detection                             │
│                                                               │
│  [ ] 3. Routing                                               │
│       ├── Configure locale prefix strategy                    │
│       ├── Set up pathname mapping (localized URLs)            │
│       ├── Implement locale switcher component                 │
│       └── Handle 404 per locale                               │
│                                                               │
│  [ ] 4. Layout & Components                                   │
│       ├── Set up html[lang] and html[dir]                     │
│       ├── Configure next-intl provider                        │
│       ├── Replace all inline strings with t() calls           │
│       └── Implement formatting (dates, numbers, currency)     │
│                                                               │
│  [ ] 5. Rich Text & Complex Content                           │
│       ├── Replace dangerouslySetInnerHTML with Trans/rich     │
│       ├── Implement ICU plural/select/ordinal rules           │
│       └── Handle variables interpolation                     │
│                                                               │
│  [ ] 6. SEO                                                   │
│       ├── Add hreflang tags to all pages                      │
│       ├── Generate localized sitemap                          │
│       ├── Set canonical URLs per locale                       │
│       ├── Localize meta titles and descriptions               │
│       └── Add localized JSON-LD structured data               │
│                                                               │
│  [ ] 7. Data Layer                                            │
│       ├── Store content per locale in database                │
│       ├── Set up locale-aware API queries                     │
│       └── Handle fallback content for untranslated entries    │
│                                                               │
│  [ ] 8. Performance                                           │
│       ├── Lazy-load translation chunks per page               │
│       ├── Set up caching (CDN, memory, localStorage)         │
│       └── Audit bundle size per locale                        │
│                                                               │
│  [ ] 9. RTL Support (if applicable)                           │
│       ├── Add html[dir] logic                                 │
│       ├── Replace physical CSS with logical properties        │
│       ├── Add Tailwind ltr:/rtl: variants                    │
│       └── Flip directional icons                             │
│                                                               │
│  [ ] 10. Error Handling                                       │
│        ├── Configure onError handler                          │
│        ├── Set up fallback locale                             │
│        ├── Handle missing translation keys gracefully         │
│        └── Monitor missing translations in production         │
│                                                               │
│  [ ] 11. Testing                                              │
│        ├── Mock translation hooks                             │
│        ├── Write snapshot tests per locale                    │
│        ├── Test locale switching                              │
│        └── Test ICU format outputs                            │
│                                                               │
│  [ ] 12. Tooling                                              │
│        ├── Set up i18n-ally (VS Code)                         │
│        ├── Add key extraction script                          │
│        ├── Add unused key detection script                    │
│        └── Add auto-sync script for new keys                  │
│                                                               │
│  [ ] 13. CI/CD                                                │
│        ├── Add translation lint step                          │
│        ├── Enforce key naming conventions                     │
│        └── Check all locales have same keys                   │
└──────────────────────────────────────────────────────────────┘
```

---

### 14. Common Troubleshooting

| Problem | Cause | Solution |
|---------|-------|----------|
| **Missing translation in production** | Key not added to all locale files | Run sync-translations script. Configure `onError` to monitor. |
| **ICU syntax error** | Missing `{` or incorrect nesting | Validate with `formatjs extract` or ICU message linter |
| **Plural rule wrong** | Using ICU plural in non-ICU parser | Ensure `i18next-icu` plugin is loaded, or use i18next native `_plural` suffix |
| **RTL layout broken** | Physical CSS properties | Replace `margin-left` → `margin-inline-start`, `padding-right` → `padding-inline-end` |
| **SEO: duplicate content**| Missing hreflang | Add `<link rel="alternate" hreflang>` to every page with all locales |
| **Canonical URL wrong**| Missing `pathnames` mapping | Define pathname overrides in `routing.ts` for localized slugs |
| **Bundle too large**| All locales bundled | Use dynamic import per locale, split namespaces per page chunk |
| **t() returns key**| Resource not loaded | Check `loadPath`, verify file exists. Use `ready` flag before rendering |
| **Interpolation not working**| Wrong syntax | i18next: `{{var}}` | next-intl: `{var}` | ICU: `{var}`. Don't mix |
| **CSR flash of untranslated content**| i18next not ready | Use Suspense, `useSuspense: true`, or `ready` state check |
| **Scripts/extract not finding keys**| Dynamic key construction | `t('prefix.' + key)` → extractor can't follow. Use static keys only |
| **Format function not found**| Custom formatter not registered | Register in `interpolation.format` config |
| **Date format mismatch**| Server vs client locale | Ensure `timeZone` and `now` are passed in `getRequestConfig` |
| **Switching locale resets state**| Unmount + remount of providers | Wait for `ready` state. Preserve URL params during switch |
| **Wrong plural for locale**| i18next doesn't have CLDR data for locale | Load locale-specific plural rules. Built-in for 190+ locales |
| **Context variable not working**| No context matcher | i18next: `t('key', { context: 'morning' })` matches `key_morning` |

#### 14.1 Debugging Checklist

```typescript
// ─── 1. Check loaded resources ───
// Browser console:
i18next.languages          // ['en', 'id']
i18next.hasResourceBundle('id', 'common')  // true/false
i18next.getResourceBundle('id', 'common')  // { ... }

// ─── 2. Verify key exists ───
i18next.exists('common:nav.home', { lng: 'id' })
// → true / false

// ─── 3. Trace resolution ───
i18next.t('common:nav.home', { lng: 'id' })
// → Returns resolved string or key itself

// ─── 4. next-intl: Check current config ───
// In console on a next-intl page:
window.__NEXT_INTL_LOCALE       // 'en' | 'id'
window.__NEXT_INTL_MESSAGES     // messages object

// ─── 5. Force re-initialization (dev only) ───
// i18next
await i18next.reloadResources()
i18next.changeLanguage('id')

// next-intl
router.replace('/id' + pathname)
```

---

### Quick Reference — Library Comparison

```
┌──────────────────────────────────────────────────────────────────────┐
│              LIBRARY COMPARISON QUICK REFERENCE                        │
│                                                                       │
│  Feature                 next-intl v4    i18next v24    vue-i18n      │
│  ─────────────────────────────────────────────────────────────         │
│  App Router SSR          ✅ Native       ⚠️ Manual       N/A          │
│  Server Components       ✅ Native       ❌ No           N/A          │
│  Static Generation       ✅ Native       ⚠️ Partial      N/A          │
│  Middleware Routing      ✅ Built-in     ❌ Manual       ❌           │
│  ICU MessageFormat       ✅ Built-in     ⚠️ Plugin       ✅ Built-in   │
│  Lazy Loading            ⚠️ Per-page     ✅ Auto         ✅ Async      │
│  Namespace Support       ⚠️ File-based   ✅ Full         ✅ Full       │
│  Plural Rules            ✅ ICU           ✅ Native       ✅ ICU        │
│  Rich Text / Trans       ✅ Built-in     ✅ Trans        ✅ v-t       │
│  Date/Number Formatting  ✅ Built-in     ❌ Manual       ✅ Built-in   │
│  RTL Support             ❌ Manual       ❌ Manual       ❌ Manual     │
│  Bundle Size             ~5KB           ~7KB           ~6KB          │
│  TypeScript              ✅ Excellent    ⚠️ Good         ⚠️ Good       │
│  Community               Medium          Large          Large         │
│  Best for                Next.js         Universal      Vue 3         │
└──────────────────────────────────────────────────────────────────────┘
```

---

### Messages JSON Format Example

```jsonc
// messages/en/common.json
{
  // ─── Site ───
  "site": {
    "name": "MyApp",
    "description": "The best platform for building products",
    "keywords": "platform, products, tools"
  },

  // ─── Navigation ───
  "nav": {
    "home": "Home",
    "about": "About",
    "articles": "Articles",
    "contact": "Contact",
    "dashboard": "Dashboard",
    "profile": "Profile",
    "settings": "Settings",
    "logout": "Log out"
  },

  // ─── Actions ───
  "actions": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "edit": "Edit",
    "create": "Create",
    "submit": "Submit",
    "search": "Search",
    "filter": "Filter",
    "download": "Download",
    "upload": "Upload",
    "share": "Share",
    "close": "Close",
    "back": "Back",
    "next": "Next",
    "retry": "Retry"
  },

  // ─── Auth ───
  "auth": {
    "welcome": "Welcome, {name}!",
    "login": "Sign In",
    "register": "Create Account",
    "logout": "Sign Out",
    "email": "Email address",
    "password": "Password"
  },

  // ─── Status ───
  "status": {
    "loading": "Loading...",
    "empty": "No data available",
    "error": "Something went wrong",
    "success": "Operation completed successfully",
    "offline": "You are offline"
  },

  // ─── Time ───
  "time": {
    "justNow": "Just now",
    "minutesAgo": "{minutes, plural, =0 {Less than a minute} one {# minute} other {# minutes}} ago",
    "hoursAgo": "{hours, plural, one {# hour} other {# hours}} ago",
    "daysAgo": "{days, plural, one {# day} other {# days}} ago"
  },

  // ─── Errors ───
  "errors": {
    "notFound": {
      "title": "Page not found",
      "description": "The page you are looking for does not exist",
      "action": "Go to homepage"
    },
    "serverError": {
      "title": "Server error",
      "description": "An unexpected error occurred. Please try again later."
    },
    "networkError": {
      "title": "Network error",
      "description": "Please check your internet connection"
    }
  }
}
```

---

### Summary

Internationalization is a **first-class architectural concern**, not a post-processing step. The four core pillars are:

1. **Routing** — Locale-aware URLs with proper redirect/cookie handling
2. **Translation** — Structured key system with ICU plurals, selects, and rich text
3. **SEO** — hreflang, canonical, sitemaps, and JSON-LD per locale
4. **UX** — RTL support, locale switching, proper date/number formatting, and accessibility

Always start with the translation file structure and namespace strategy before writing any component code. Choose the library that fits your framework: `next-intl` for Next.js, `i18next` for universal apps, `vue-i18n` for Vue, or `svelte-i18n` for Svelte. Never inline strings, never hardcode locale-specific formatting, and always test with at least one RTL locale (Arabic) to catch layout issues early.
