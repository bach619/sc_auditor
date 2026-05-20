---
name: cms-sanity
description: Sanity CMS mastery — schema design, GROQ queries, Sanity Studio, content modeling, Next.js integration, preview, internationalization, assets, and production patterns
license: MIT
compatibility: opencode
metadata:
  audience: frontend-developers
  domain: frontend
  paradigm: headless-cms
  capabilities:
    - content-modeling
    - schema-design
    - groq-queries
    - sanity-studio
    - nextjs-integration
    - preview-patterns
    - internationalization
    - asset-management
    - performance-optimization
  integrates_with:
    - frontend-react
    - typescript
    - frontend-tailwind
---

# Sanity CMS v3 — Opencode God-Tier Skill

## 1. Content Modeling Philosophy

### Document vs Object Types

| | Document | Object |
|---|---|---|
| Identity | `_id`, `_createdAt`, `_updatedAt` autonumeric | No identity, embedded |
| Queries | Top-level `*[_type == "x"]` | Only accessible via parent |
| References | Can be `_ref`-ed | Cannot be referenced |
| History | Full revision history | No history |
| Strengths | Independent content that needs references, publishing workflow | Nested structured data, reusable field groups |
| When to use | Pages, posts, authors, products, settings | Address, SEO meta, link, rich text blocks, image with caption |

### Schema Design Decision Tree

```
Is this content independent?
  ├── YES → Does it need its own URL / be shared by multiple parents?
  │   ├── YES → Document type (e.g. Author, Category)
  │   └── NO → Is it a translatable field group?
  │       ├── YES → Object type (e.g. SEO, Address)
  │       └── NO → Inline fields
  └── NO → Is it used in >2 places?
      ├── YES → Object type (e.g. Link, CallToAction)
      └── NO → Inline fields
```

### Relationship Patterns

**Single Reference** — one-to-one:
```ts
defineField({
  name: 'author',
  type: 'reference',
  to: [{ type: 'author' }],
})
```

**Array of References** — one-to-many:
```ts
defineField({
  name: 'categories',
  type: 'array',
  of: [{ type: 'reference', to: [{ type: 'category' }] }],
})
```

**Cross-Dataset References** (Sanity Connect):
```ts
defineField({
  name: 'externalProduct',
  type: 'crossDatasetReference',
  dataset: 'production',
  studioUrl: ({ id }) => `https://my-studio.sanity.studio/desk/product;${id}`,
  to: [
    {
      type: 'product',
      preview: {
        select: { title: 'name', subtitle: 'sku' },
      },
    },
  ],
})
```

### Singleton Pattern

```ts
// singletons/siteSettings.ts
import { defineType, defineField } from 'sanity'

export default defineType({
  name: 'siteSettings',
  title: 'Site Settings',
  type: 'document',
  __experimental_actions: ['update', 'publish'],
  fields: [
    defineField({ name: 'title', type: 'string' }),
    defineField({ name: 'description', type: 'text' }),
    defineField({ name: 'logo', type: 'image' }),
    defineField({ name: 'socialLinks', type: 'array', of: [{ type: 'socialLink' }] }),
  ],
})
```

Structure builder enforcing singleton:
```ts
// studio/structure.ts
import { StructureBuilder } from 'sanity/structure'

export const structure = (S: StructureBuilder) =>
  S.list()
    .title('Content')
    .items([
      S.listItem()
        .title('Site Settings')
        .icon(() => <CogIcon />)
        .child(
          S.document()
            .schemaType('siteSettings')
            .documentId('siteSettings')
        ),
      S.divider(),
      ...S.documentTypeListItems().filter(
        (item) => item.getId() !== 'siteSettings'
      ),
    ])
```

### Modular Block Content

```ts
// blocks/blockContent.ts
export default defineType({
  name: 'blockContent',
  title: 'Block Content',
  type: 'array',
  of: [
    {
      type: 'block',
      styles: [
        { title: 'Normal', value: 'normal' },
        { title: 'H2', value: 'h2' },
        { title: 'H3', value: 'h3' },
        { title: 'H4', value: 'h4' },
        { title: 'Quote', value: 'blockquote' },
      ],
      lists: [{ title: 'Bullet', value: 'bullet' }, { title: 'Numbered', value: 'number' }],
      marks: {
        decorators: [
          { title: 'Bold', value: 'strong' },
          { title: 'Italic', value: 'em' },
          { title: 'Code', value: 'code' },
        ],
        annotations: [
          { name: 'link', type: 'object', fields: [
            { name: 'href', type: 'url' },
            { name: 'openInNewTab', type: 'boolean' },
          ]},
          { name: 'internalLink', type: 'reference', to: [{ type: 'page' }, { type: 'post' }] },
        ],
      },
    },
    { type: 'imageBlock' },
    { type: 'codeBlock' },
    { type: 'callout' },
    { type: 'embed' },
  ],
})
```

---

## 2. Schema Design (God-Tier)

### Core Document Schema — Blog Post

```ts
// schemas/post.ts
import { defineType, defineField } from 'sanity'

export default defineType({
  name: 'post',
  title: 'Post',
  type: 'document',
  groups: [
    { name: 'content', title: 'Content' },
    { name: 'seo', title: 'SEO' },
    { name: 'settings', title: 'Settings' },
  ],
  fields: [
    defineField({
      name: 'title',
      title: 'Title',
      type: 'string',
      group: 'content',
      validation: (rule) => rule.required().min(10).max(120).warning('Titles under 120 chars rank better on SEO'),
    }),
    defineField({
      name: 'slug',
      title: 'Slug',
      type: 'slug',
      group: 'settings',
      options: { source: 'title', maxLength: 96 },
      validation: (rule) => rule.required(),
    }),
    defineField({
      name: 'author',
      title: 'Author',
      type: 'reference',
      to: [{ type: 'author' }],
      group: 'content',
    }),
    defineField({
      name: 'categories',
      title: 'Categories',
      type: 'array',
      of: [{ type: 'reference', to: [{ type: 'category' }] }],
      group: 'content',
    }),
    defineField({
      name: 'publishedAt',
      title: 'Published At',
      type: 'datetime',
      group: 'settings',
      initialValue: () => new Date().toISOString(),
    }),
    defineField({
      name: 'excerpt',
      title: 'Excerpt',
      type: 'text',
      rows: 3,
      group: 'content',
      validation: (rule) => rule.max(300),
    }),
    defineField({
      name: 'coverImage',
      title: 'Cover Image',
      type: 'image',
      group: 'content',
      options: { hotspot: true },
      fields: [
        { name: 'alt', type: 'string', title: 'Alt Text' },
        { name: 'caption', type: 'string', title: 'Caption' },
      ],
    }),
    defineField({
      name: 'body',
      title: 'Body',
      type: 'blockContent',
      group: 'content',
    }),
    defineField({
      name: 'seo',
      title: 'SEO',
      type: 'seoMeta',
      group: 'seo',
    }),
    defineField({
      name: 'featured',
      title: 'Featured Post',
      type: 'boolean',
      group: 'settings',
      initialValue: false,
    }),
  ],
  orderings: [
    {
      title: 'Publish Date',
      name: 'publishedAtDesc',
      by: [{ field: 'publishedAt', direction: 'desc' }],
    },
    {
      title: 'Title',
      name: 'titleAsc',
      by: [{ field: 'title', direction: 'asc' }],
    },
  ],
  preview: {
    select: {
      title: 'title',
      subtitle: 'publishedAt',
      media: 'coverImage',
    },
    prepare({ title, subtitle, media }) {
      return {
        title: title || 'Untitled',
        subtitle: subtitle ? new Date(subtitle).toLocaleDateString() : '',
        media,
      }
    },
  },
})
```

### Author Schema

```ts
// schemas/author.ts
import { defineType, defineField } from 'sanity'
import { UserIcon } from '@heroicons/react/24/outline'

export default defineType({
  name: 'author',
  title: 'Author',
  type: 'document',
  icon: UserIcon,
  fields: [
    defineField({
      name: 'name',
      title: 'Name',
      type: 'string',
      validation: (rule) => rule.required(),
    }),
    defineField({
      name: 'slug',
      title: 'Slug',
      type: 'slug',
      options: { source: 'name' },
    }),
    defineField({
      name: 'image',
      title: 'Image',
      type: 'image',
      options: { hotspot: true },
    }),
    defineField({
      name: 'bio',
      title: 'Bio',
      type: 'array',
      of: [{ type: 'block' }],
    }),
    defineField({
      name: 'role',
      title: 'Role',
      type: 'string',
      options: {
        list: [
          { title: 'Editor', value: 'editor' },
          { title: 'Writer', value: 'writer' },
          { title: 'Contributor', value: 'contributor' },
        ],
      },
    }),
  ],
  preview: {
    select: { title: 'name', subtitle: 'role', media: 'image' },
  },
})
```

### Custom Field Type — localeString

```ts
// objects/localeString.ts
import { defineType, defineField } from 'sanity'

export default defineType({
  name: 'localeString',
  title: 'Localized String',
  type: 'object',
  fields: [
    defineField({ name: 'id', title: 'Indonesian', type: 'string' }),
    defineField({ name: 'en', title: 'English', type: 'string' }),
    defineField({ name: 'zh', title: 'Chinese', type: 'string' }),
    defineField({ name: 'ja', title: 'Japanese', type: 'string' }),
  ],
})
```

### Custom Field Type — Color Picker

```ts
// objects/color.ts
import { defineType } from 'sanity'

export default defineType({
  name: 'color',
  title: 'Color',
  type: 'object',
  fields: [
    { name: 'hex', type: 'string', title: 'Hex' },
    { name: 'alpha', type: 'number', title: 'Alpha', initialValue: 100 },
  ],
  preview: {
    select: { hex: 'hex' },
    prepare({ hex }: { hex: string }) {
      return { title: hex, media: () => <div style={{ backgroundColor: hex, width: '1em', height: '1em', borderRadius: '4px' }} /> }
    },
  },
})
```

### Advanced Validation

```ts
defineField({
  name: 'sku',
  title: 'SKU',
  type: 'string',
  validation: (rule) =>
    rule
      .required()
      .regex(/^[A-Z]{2}-\d{4}-\d{3}$/, { name: 'SKU format', invert: false })
      .custom((sku, context) => {
        if (!sku) return true
        const isDuplicate = context.document?.sku || context.document?._id
        if (sku === isDuplicate) return true
        return 'SKU must be unique across all products'
      }),
})
```

### Field Groups for Complex Schemas

```ts
defineField({
  name: 'pricing',
  title: 'Pricing',
  type: 'object',
  group: 'commerce',
  fieldsets: [
    { name: 'retail', title: 'Retail', options: { columns: 2 } },
    { name: 'wholesale', title: 'Wholesale', options: { columns: 2 } },
  ],
  fields: [
    defineField({ name: 'price', type: 'number', fieldset: 'retail', validation: (r) => r.required().min(0) }),
    defineField({ name: 'compareAt', type: 'number', fieldset: 'retail' }),
    defineField({ name: 'wholesalePrice', type: 'number', fieldset: 'wholesale' }),
    defineField({ name: 'minWholesaleQty', type: 'number', fieldset: 'wholesale' }),
    defineField({ name: 'taxRate', type: 'number' }),
    defineField({ name: 'currency', type: 'string', initialValue: 'USD' }),
  ],
})
```

### Initial Value Functions

```ts
defineField({
  name: 'publishedAt',
  type: 'datetime',
  initialValue: () => new Date().toISOString(),
})

defineField({
  name: 'language',
  type: 'string',
  initialValue: () => {
    const now = new Date()
    const hours = now.getHours()
    return hours < 12 ? 'en' : 'id'
  },
})
```

### Custom Document Actions — Workflow States

```ts
// actions/workflowActions.ts
import { definePlugin } from 'sanity'
import { type DocumentActionComponent } from 'sanity'

const WORKFLOW_STATES = ['draft', 'review', 'approved', 'published', 'archived'] as const

export const workflowActions = definePlugin({
  name: 'workflow-actions',
  document: {
    actions: (prev, context) => {
      const doc = context.draft || context.published
      const currentState = doc?.workflowState || 'draft'

      return [
        ...prev,
        {
          label: `Move to ${WORKFLOW_STATES[WORKFLOW_STATES.indexOf(currentState) + 1] || 'archived'}`,
          icon: () => '→',
          onHandle: async ({ id, type }) => {
            const nextState = WORKFLOW_STATES[WORKFLOW_STATES.indexOf(currentState) + 1] || 'archived'
            await context.client
              .patch(id)
              .set({ workflowState: nextState })
              .commit()
          },
        },
      ] satisfies DocumentActionComponent[]
    },
  },
})
```

---

## 3. GROQ Query Language (Mastery)

### Fundamentals

```groq
// Select all posts
*[_type == "post"]

// Select single document by ID
*[_id == "abc123"][0]

// Count all documents of a type
count(*[_type == "post"])

// Distinct values
*[_type == "post"].category->name
```

### Projections

```groq
// Simple projection
*[_type == "post"]{
  title,
  slug,
  publishedAt
}

// Rename fields
*[_type == "post"]{
  "judul": title,
  "slug": slug.current,
  "tanggal": publishedAt
}

// Nested projections with dereference
*[_type == "post"]{
  title,
  "author": author->{name, image},
  "categories": categories[]->{title, slug}
}

// Spread syntax
*[_type == "post"]{
  ...,
  "author": author->name
}

// Object composition
*[_type == "page"]{
  title,
  "metadata": {
    "url": "/" + slug.current,
    "type": _type,
    "id": _id
  }
}
```

### Filters — Deep Dive

```groq
// Equality
*[_type == "post"]

// NOT
*[_type == "post" && _id != "drafts." + $currentId]

// IN array
*[_type == "post" && _id in $ids]

// MATCH (text search — uses tokenized index)
*[_type == "post" && title match "sanity*"]

// DEFINED (field exists and isn't null)
*[_type == "post" && defined(publishedAt)]

// REFERENCES (documents that reference a specific doc)
*[_type == "post" && references($authorId)]

// Range
*[_type == "product" && price >= 100 && price <= 500]

// Date range
*[_type == "post" && publishedAt > "2026-01-01T00:00:00Z"]

// Multiple conditions
*[_type == "product" && (category->slug.current == "shoes" || category->slug.current == "boots") && price > 50]
```

### Joins — Dereference (`->`) and Parent Reference (`^`)

```groq
// Single dereference
*[_type == "post"]{author->name}

// Double dereference
*[_type == "post"]{
  "author": author->{name, "department": department->name}
}

// Array dereference
*[_type == "post"]{
  "categories": categories[]->{title, slug}
}

// Parent reference in subquery (^)
*[_type == "page"]{
  title,
  "sections": sections[]{
    ...,
    "linkCount": count(*[_type == "link" && references(^._id)])
  }
}

// Nested parent reference
*[_type == "product"]{
  name,
  "variants": variants[]{
    sku,
    "relatedCount": count(*[_type == "product" && references(^._id)])
  }
}
```

### Aggregations

```groq
// Count total products
count(*[_type == "product"])

// Count with filter
count(*[_type == "post" && publishedAt > "2026-01-01T00:00:00Z"])

// Group by category
{
  "categories": *[_type == "category"]{
    title,
    "count": count(*[_type == "post" && references(^._id)])
  }
}

// Numeric aggregations
*[_type == "product"]{
  "totalValue": sum(price),
  "avgPrice": avg(price),
  "maxPrice": max(price),
  "minPrice": min(price)
}[0]

// Date aggregations
*[_type == "post"]{
  "year": round(dateTime(publishedAt).year),
  "month": round(dateTime(publishedAt).month)
}
```

### Subqueries

```groq
// Conditional with select
*[_type == "post"]{
  title,
  "status": select(
    defined(publishedAt) => "published",
    defined(_updatedAt) => "draft",
    "unknown"
  )
}

// Nested subqueries
*[_type == "post"]{
  title,
  "latestPosts": *[_type == "post" && _id != ^._id] | order(publishedAt desc) [0..4]{
    title, slug
  }
}

// Aggregation subquery
*[_type == "category"]{
  title,
  "posts": *[_type == "post" && references(^._id)]{title, slug}
}
```

### GROQ Functions

```groq
// coalesce — first non-null value
*[_type == "post"]{
  "displayTitle": coalesce(seo.title, title, "Untitled")
}

// round
*[_type == "product"]{
  "roundedPrice": round(price)
}

// dateTime operations
*[_type == "post"]{
  "age": round((now() - dateTime(publishedAt)) / (60 * 60 * 24)) + " days ago"
}

// string functions
*[_type == "post"]{
  "slug": string::split(slug.current, "-"),
  "upper": string::upper(title),
  "lower": string::lower(title)
}

// pt::text — extract plain text from Portable Text
*[_type == "post"]{
  title,
  "plainExcerpt": pt::text(body)[0..200]
}

// pt::level — get block levels
*[_type == "post"]{
  "headings": pt::level(body, ["h2", "h3"])
}

// array::join
*[_type == "post"]{
  "tagString": array::join(tags[]->name, ", ")
}

// global::now
*[_type == "post" && publishedAt < now()]

// length
*[_type == "post"]{
  "wordCount": length(pt::text(body))
}
```

### Ordering & Pagination

```groq
// Sort by field
*[_type == "post"] | order(publishedAt desc)

// Multi-field sort
*[_type == "post"] | order(featured desc, publishedAt desc)

// Sort by related data
*[_type == "post"] | order(author->name asc)

// Pagination
*[_type == "post"] | order(publishedAt desc) [0..19]    // page 1, 20 items
*[_type == "post"] | order(publishedAt desc) [20..39]   // page 2

// Single item
*[_type == "post" && slug.current == $slug][0]

// Random order (limited use)
*[_type == "post"] | order(_id asc) [0..5]

// Grouped sort
*[_type == "post"] | order(coalesce(publishedAt, _createdAt) desc)
```

### Parameterized Queries

```groq
// Single param
const query = `*[_type == "post" && slug.current == $slug][0]`

// Multiple params
const query = `*[_type == $type && publishedAt < $now] | order(publishedAt desc) [$start...$end]`

// Array param
const query = `*[_type == "post" && _id in $ids]{title, slug}`

// With GROQ functions
const query = `*[_type == "product" && price >= $minPrice && price <= $maxPrice]{name, price}`
```

### Performance — Query Optimization

```groq
// BAD — full scan then filter
*[_type == "page" || _type == "post" || _type == "product"] | order(_updatedAt desc) [0..10]

// GOOD — filter first, paginate, then union
{
  "pages": *[_type == "page"][0..10]{_type, title},
  "posts": *[_type == "post"][0..10]{_type, title},
  "products": *[_type == "product"][0..10]{_type, title}
}

// BAD — fetch everything just to count
*[_type == "post"] | order(publishedAt desc) [0..9]{...}

// GOOD — optimized count + projection
{
  "total": count(*[_type == "post"]),
  "posts": *[_type == "post"] | order(publishedAt desc) [0..9]{
    title, slug, excerpt, "author": author->name
  }
}

// BAD — deep chained dereferences in large datasets
*[_type == "post"]{category->tag->group->name}

// GOOD — batch dereferences in projections
*[_type == "post"]{
  "categoryName": category->tag->group->name
}
```

### GROQ vs GraphQL

| Aspect | GROQ | GraphQL |
|--------|------|---------|
| Learning curve | Minimal | Moderate |
| Type safety | Via codegen | Native |
| Filters | Declarative `match`, `references()` | Requires resolvers |
| Aggregations | Native `count()`, `sum()`, `avg()` | Requires resolvers/stitching |
| Nested deref | `->` operator | Nested queries |
| Client size | Tiny (~5KB) | Larger |
| Real-time | Through listener API | Subscriptions |
| Best for | Direct Sanity operations, content queries | Complex federated APIs, multi-source |

---

## 4. Sanity Studio Customization

### Structure Builder — Full Desk Structure

```ts
// studio/structure.ts
import { StructureBuilder, StructureResolver } from 'sanity/structure'
import { CogIcon, DocumentIcon, EyeOpenIcon, FolderIcon } from '@sanity/icons'

export const structure: StructureResolver = (S, context) => {
  const { currentUser } = context

  return S.list()
    .title('Content')
    .items([
      S.listItem()
        .title('Site Settings')
        .icon(CogIcon)
        .child(
          S.editor()
            .id('siteSettings')
            .schemaType('siteSettings')
            .documentId('siteSettings')
        ),
      S.divider(),
      S.listItem()
        .title('Blog')
        .icon(DocumentIcon)
        .child(
          S.list()
            .title('Blog')
            .items([
              S.documentTypeListItem('post').title('Posts').icon(DocumentIcon),
              S.documentTypeListItem('category').title('Categories').icon(FolderIcon),
              S.documentTypeListItem('author').title('Authors').icon(FolderIcon),
            ])
        ),
      S.documentTypeListItem('page').title('Pages'),
      S.documentTypeListItem('product').title('Products'),
      S.divider(),
      S.listItem()
        .title('Drafts Review')
        .icon(EyeOpenIcon)
        .child(
          S.documentList()
            .title('Pending Review')
            .filter('_type in ["post", "page"] && workflowState == "review"')
            .params({})
        ),
    ])
}
```

### Custom Document List with Filters

```ts
// studio/structure.ts — filtered views
S.documentTypeListItem('post').child(
  S.documentList()
    .title('Posts')
    .filter('_type == "post"')
    .initialValueTemplates([S.initialValueTemplateItem('post')])
    .menuItems([
      ...S.documentTypeList('post').getMenuItems(),
      S.menuItem()
        .title('Show Featured Only')
        .icon(() => '★')
        .action('toggleFeaturedFilter')
        .params({ featured: true }),
    ])
    .canHandleIntent((intent, context) => {
      if (intent === 'toggleFeaturedFilter') {
        // Custom filter toggle logic
        return true
      }
      return false
    })
)
```

### Custom Input Component — Slug Preview

```tsx
// components/SlugPreview.tsx
import { type StringInputProps, set, unset } from 'sanity'
import { Stack, Text, Card, Flex, Button } from '@sanity/ui'
import { useEffect, useState } from 'react'

export function SlugInput(props: StringInputProps) {
  const { value, onChange, elementProps } = props
  const [previewUrl, setPreviewUrl] = useState('')

  useEffect(() => {
    if (value) {
      setPreviewUrl(`https://example.com/${value}`)
    }
  }, [value])

  return (
    <Stack space={2}>
      <input {...elementProps} />
      {previewUrl && (
        <Card padding={2} tone="positive" radius={2}>
          <Flex gap={2} align="center">
            <Text size={1}>Preview: </Text>
            <Text size={1} muted>
              {previewUrl}
            </Text>
            <Button
              fontSize={1}
              text="Copy"
              mode="ghost"
              onClick={() => navigator.clipboard.writeText(previewUrl)}
            />
          </Flex>
        </Card>
      )}
    </Stack>
  )
}
```

```ts
// schema field registration
defineField({
  name: 'slugPreview',
  type: 'string',
  components: { input: SlugInput },
})
```

### Custom Preview Components

```tsx
// components/PostPreview.tsx
import { PreviewProps } from 'sanity'
import { Flex, Text, Card } from '@sanity/ui'

export function PostPreview(props: PreviewProps) {
  const { title, subtitle, media } = props

  return (
    <Card padding={2} radius={2}>
      <Flex gap={3} align="center">
        {media && <div style={{ width: 40, height: 40, borderRadius: 4, overflow: 'hidden' }}>{media}</div>}
        <Flex direction="column" flex={1}>
          <Text size={1} weight="semibold">{title}</Text>
          <Text size={0} muted>{subtitle}</Text>
        </Flex>
        <Text size={0} weight="medium" muted>
          {new Date().toLocaleDateString()}
        </Text>
      </Flex>
    </Card>
  )
}

// Schema registration
export default defineType({
  name: 'post',
  // ...
  preview: {
    select: { title: 'title', subtitle: 'excerpt', media: 'coverImage' },
    prepare: (selection) => selection,
  },
  components: { preview: PostPreview },
})
```

### Studio Theming

```ts
// sanity.config.ts
import { defineConfig } from 'sanity'
import { buildLegacyTheme } from 'sanity'

const customTheme = buildLegacyTheme({
  '--brand-primary': '#c96442',
  '--brand-secondary': '#7c3aed',
  '--main-navigation-color': '#18181b',
  '--main-navigation-color--inverted': '#ffffff',
  '--focus-color': '#c96442',
  '--default-button-color': '#c96442',
  '--default-button-primary-color': '#c96442',
  '--default-button-success-color': '#22c55e',
  '--default-button-warning-color': '#f59e0b',
  '--default-button-danger-color': '#ef4444',
})

export default defineConfig({
  name: 'default',
  title: 'My CMS',
  projectId: 'your-project-id',
  dataset: 'production',
  theme: customTheme,
  studio: {
    components: {
      logo: () => <strong style={{ color: '#c96442' }}>MyCMS</strong>,
      navbar: CustomNavbar,
      toolMenu: CustomToolMenu,
    },
  },
})
```

### Custom Plugins — Dashboard Widget

```ts
// plugins/dashboardWidget/index.ts
import { definePlugin } from 'sanity'
import { DashboardWidget } from '@sanity/dashboard'

const ContentOverviewWidget = () => (
  <DashboardWidget title="Content Overview">
    <div>Total posts: ...</div>
    <div>Pending reviews: ...</div>
    <div>Recent updates: ...</div>
  </DashboardWidget>
)

export const contentDashboard = definePlugin({
  name: 'content-dashboard',
  dashboard: {
    widgets: [
      { name: 'content-overview', component: ContentOverviewWidget },
    ],
  },
})
```

### Custom Tool

```ts
// tools/importTool.tsx
import { definePlugin } from 'sanity'
import { Tool } from 'sanity'
import { ImportIcon } from '@sanity/icons'
import { ImportPanel } from './ImportPanel'

export const importTool = definePlugin({
  name: 'import',
  tools: (prev) => [
    ...prev,
    {
      name: 'import',
      title: 'Import',
      icon: ImportIcon,
      component: ImportPanel,
    } satisfies Tool,
  ],
})
```

### Role-Based Access Control

```ts
// sanity.config.ts — custom roles
export default defineConfig({
  // ...
  auth: {
    loginMethod: 'dual',
  },
  acl: {
    roles: [
      {
        name: 'editor',
        title: 'Editor',
        description: 'Can create/edit but not publish or delete',
        permissions: [
          { name: 'create', filter: '_type == "post" || _type == "page"' },
          { name: 'edit', filter: '_type == "post" || _type == "page"' },
          { name: 'read', filter: true },
        ],
      },
      {
        name: 'publisher',
        title: 'Publisher',
        description: 'Full access to all content',
        permissions: [
          { name: 'create', filter: true },
          { name: 'edit', filter: true },
          { name: 'publish', filter: true },
          { name: 'delete', filter: true },
          { name: 'read', filter: true },
        ],
      },
    ],
  },
})
```

---

## 5. Next.js + Sanity Integration

### Setup — Client Configuration

```ts
// lib/sanity/client.ts
import { createClient } from 'next-sanity'
import { apiVersion, dataset, projectId, useCdn } from './env'

export const client = createClient({
  projectId,
  dataset,
  apiVersion, // 2024-01-01 or latest
  useCdn,     // true for production (CDN cached), false for preview
  perspective: 'published',
})

// lib/sanity/env.ts
export const projectId = process.env.NEXT_PUBLIC_SANITY_PROJECT_ID!
export const dataset = process.env.NEXT_PUBLIC_SANITY_DATASET!
export const apiVersion = process.env.NEXT_PUBLIC_SANITY_API_VERSION || '2024-01-01'
export const useCdn = process.env.NODE_ENV === 'production'
```

### Typed Fetch Helper

```ts
// lib/sanity/fetch.ts
import 'server-only'
import { client } from './client'
import type { QueryParams } from '@sanity/client'
import { draftMode } from 'next/headers'

export async function sanityFetch<QueryResult>({
  query,
  params = {},
  tags,
}: {
  query: string
  params?: QueryParams
  tags?: string[]
}): Promise<QueryResult> {
  const isDraftMode = (await draftMode()).isEnabled

  if (isDraftMode) {
    return client.fetch<QueryResult>(query, params, {
      perspective: 'previewDrafts',
      useCdn: false,
      stega: true,
    })
  }

  return client.fetch<QueryResult>(query, params, {
    cache: 'force-cache',
    next: { tags },
  })
}
```

### Static Generation with GROQ

```ts
// app/(blog)/posts/[slug]/page.tsx
import { sanityFetch } from '@/lib/sanity/fetch'
import { groq } from 'next-sanity'

const POST_QUERY = groq`*[_type == "post" && slug.current == $slug][0]{
  title,
  slug,
  publishedAt,
  body,
  "author": author->{name, image},
  "categories": categories[]->{title, slug}
}`

const POSTS_SLUGS_QUERY = groq`*[_type == "post" && defined(slug.current)]{
  "slug": slug.current
}`

export async function generateStaticParams() {
  const posts = await sanityFetch<{ slug: string }[]>({
    query: POSTS_SLUGS_QUERY,
    tags: ['post'],
  })
  return posts.map((post) => ({ slug: post.slug }))
}

export default async function PostPage({
  params,
}: {
  params: Promise<{ slug: string }>
}) {
  const { slug } = await params
  const post = await sanityFetch<Post>({
    query: POST_QUERY,
    params: { slug },
    tags: [`post:${slug}`],
  })

  if (!post) return notFound()

  return <PostRenderer post={post} />
}
```

### ISR — Incremental Static Regeneration

```ts
// lib/sanity/fetch.ts (ISR variant)
const isDraftMode = (await draftMode()).isEnabled

if (isDraftMode) {
  return client.fetch<QueryResult>(query, params, {
    perspective: 'previewDrafts',
    useCdn: false,
    stega: true,
  })
}

// Production: ISR with tags
return client.fetch<QueryResult>(query, params, {
  next: {
    tags,
    revalidate: 60, // fallback revalidation every 60s
  },
})
```

### Real-Time Preview with useLiveQuery

```ts
// components/preview/PostPreviewWrapper.tsx
'use client'

import { useLiveQuery } from '@sanity/preview-kit'
import { PostRenderer } from './PostRenderer'

const POST_QUERY = groq`*[_type == "post" && slug.current == $slug][0]{
  title, body, "author": author->name
}`

export function PostPreviewWrapper({ initialData, slug }: {
  initialData: Post
  slug: string
}) {
  const [data] = useLiveQuery(initialData, POST_QUERY, { slug })

  return <PostRenderer post={data} />
}
```

### Draft Mode — Next.js Route Handler

```ts
// app/api/draft/route.ts
import { draftMode } from 'next/headers'
import { redirect } from 'next/navigation'
import { client } from '@/lib/sanity/client'

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const secret = searchParams.get('secret')
  const slug = searchParams.get('slug')
  const type = searchParams.get('type')

  if (secret !== process.env.SANITY_PREVIEW_SECRET) {
    return new Response('Invalid token', { status: 401 })
  }

  const doc = await client.fetch(
    `*[_type == $type && slug.current == $slug][0]{_id, slug}`,
    { type, slug }
  )

  if (!doc) {
    return new Response('Document not found', { status: 404 })
  }

  ;(await draftMode()).enable()
  redirect(`/${type === 'post' ? 'blog/' : ''}${doc.slug.current}`)
}
```

### Preview URL in Sanity Studio

```ts
// sanity.config.ts
const previewUrl = (doc: { _type: string; slug?: { current: string } }) => {
  if (!doc?.slug?.current) return ''
  const base = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000'
  const segment = doc._type === 'post' ? 'blog' : doc._type
  return `${base}/${segment}/${doc.slug.current}`
}

export default defineConfig({
  // ...
  document: {
    productionUrl: async (prev, context) => {
      const { document } = context
      return previewUrl(document as any)
    },
  },
})
```

### Webhook-Based Revalidation

```ts
// app/api/revalidate/route.ts
import { revalidateTag } from 'next/cache'
import { NextRequest, NextResponse } from 'next/server'

export async function POST(request: NextRequest) {
  const signature = request.headers.get('sanity-webhook-signature')
  const secret = process.env.SANITY_WEBHOOK_SECRET

  if (!signature || signature !== secret) {
    return NextResponse.json({ error: 'Invalid signature' }, { status: 401 })
  }

  const body = await request.json()
  const { _type, slug } = body

  // Revalidate by tag
  revalidateTag(_type)

  if (slug?.current) {
    revalidateTag(`${_type}:${slug.current}`)
  }

  return NextResponse.json({ revalidated: true })
}
```

### Type-Safe GROQ with Custom Codegen

```ts
// @sanity-codegen generated types
export interface Post {
  _id: string
  _type: 'post'
  _createdAt: string
  _updatedAt: string
  title?: string
  slug?: { current: string }
  author?: Author
  categories?: Category[]
  body?: PortableTextBlock[]
  excerpt?: string
  publishedAt?: string
}

export interface Author {
  _id: string
  _type: 'author'
  name?: string
  image?: SanityImageSource
  bio?: PortableTextBlock[]
}

// Custom type generation with typed GROQ
const query = groq`*[_type == "post"]{
  _id, title, slug, "author": author->name
}`

type PostListItem = ExtractResult<typeof query>
// { _id: string; title: string | null; slug: { current: string } | null; author: string | null }
```

---

## 6. Internationalization

### Document-Level Translation Plugin

```ts
// sanity.config.ts
import { documentInternationalization } from '@sanity/document-internationalization'

export default defineConfig({
  plugins: [
    documentInternationalization({
      supportedLanguages: [
        { id: 'id', title: 'Indonesian' },
        { id: 'en', title: 'English' },
        { id: 'zh', title: 'Chinese' },
        { id: 'ja', title: 'Japanese' },
      ],
      schemaTypes: ['post', 'page', 'product'],
      languageField: 'language',
    }),
  ],
})
```

### Schema-Based Localized Strings

```ts
// objects/localeString.ts
export default defineType({
  name: 'localeString',
  title: 'Localized String',
  type: 'object',
  fieldsets: [
    { name: 'translations', title: 'Translations', options: { columns: 2 } },
  ],
  fields: [
    { name: 'id', type: 'string', title: 'Bahasa Indonesia', fieldset: 'translations' },
    { name: 'en', type: 'string', title: 'English', fieldset: 'translations' },
    { name: 'zh', type: 'string', title: '中文', fieldset: 'translations' },
    { name: 'ja', type: 'string', title: '日本語', fieldset: 'translations' },
  ],
})
```

### LocaleBlock for Rich Text

```ts
// objects/localeBlock.ts
export default defineType({
  name: 'localeBlock',
  title: 'Localized Block Content',
  type: 'object',
  fields: [
    { name: 'id', type: 'blockContent', title: 'Bahasa Indonesia' },
    { name: 'en', type: 'blockContent', title: 'English' },
  ],
})
```

### Field-Level Translation Strategy

```ts
// Schema with mixed translation strategy
export default defineType({
  name: 'page',
  title: 'Page',
  type: 'document',
  fields: [
    // Document-level: each locale is a separate document
    defineField({
      name: 'language',
      type: 'string',
      readOnly: true,
      hidden: true,
    }),

    // Field-level: one field per locale (good for SEO metadata)
    defineField({
      name: 'seoTitle',
      title: 'SEO Title',
      type: 'localeString',
    }),

    // Field-level: single content with localeBlock
    defineField({
      name: 'body',
      title: 'Body',
      type: 'localeBlock',
    }),

    // Shared across all locales
    defineField({
      name: 'slug',
      title: 'Slug',
      type: 'slug',
    }),

    // Shared reference
    defineField({
      name: 'author',
      title: 'Author',
      type: 'reference',
      to: [{ type: 'author' }],
    }),
  ],
})
```

### GROQ Queries for Translated Content

```groq
// Fetch single locale (document-level translation)
*[_type == "page" && slug.current == $slug && language == $locale][0]

// Fetch with fallback
*[_type == "page" && slug.current == $slug] | order(
  select(language == $locale => 0, language == "en" => 1, 2)
) [0]

// Fetch all available languages for a page
*[_type == "page" && slug.current == $slug]{
  "translations": language,
  _id, title
}

// Field-level: coalesce across locales
*[_type == "page" && slug.current == $slug][0]{
  "title": coalesce(seoTitle[$locale], seoTitle["en"], "Untitled"),
  "body": coalesce(body[$locale], body["en"])
}
```

### Fallback Language Strategy

```ts
// lib/sanity/localizedFetch.ts
import { sanityFetch } from './fetch'

export async function localizedFetch<T>({
  query,
  locale,
  fallback = 'en',
  params = {},
}: {
  query: string
  locale: string
  fallback?: string
  params?: Record<string, unknown>
}): Promise<T> {
  // Try requested locale
  const result = await sanityFetch<T>({
    query: `${query} && language == $locale`,
    params: { ...params, locale },
  })

  if (result) return result

  // Fallback to default
  return sanityFetch<T>({
    query: `${query} && language == $fallback`,
    params: { ...params, locale: fallback },
  })
}
```

---

## 7. Asset Management

### Image Optimization — URL Builder

```ts
// lib/sanity/image.ts
import imageUrlBuilder from '@sanity/image-url'
import { client } from './client'
import type { SanityImageSource } from '@sanity/image-url/lib/types/types'

const builder = imageUrlBuilder(client)

export function imageUrl(source: SanityImageSource) {
  return builder.image(source)
}

// Usage
imageUrl(post.coverImage)
  .width(1200)
  .height(630)
  .format('webp')
  .quality(85)
  .fit('crop')
  .url()
// -> https://cdn.sanity.io/images/{project}/{dataset}/{imageHash}-{crop}-{hotspot}.webp?w=1200&h=630&q=85&fit=crop
```

### Responsive Image Component

```tsx
// components/SanityImage.tsx
import Image from 'next/image'
import { imageUrl } from '@/lib/sanity/image'
import type { SanityImageSource } from '@sanity/image-url/lib/types/types'

interface Props {
  image: SanityImageSource & { alt?: string }
  priority?: boolean
  className?: string
}

export function SanityImage({ image, priority, className }: Props) {
  if (!image) return null

  const url = imageUrl(image)
  const alt = image.alt || ''

  // Generate srcSet
  const sizes = [360, 640, 768, 1024, 1280, 1536, 1920]

  return (
    <Image
      src={url.width(1920).quality(85).url()}
      alt={alt}
      sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
      priority={priority}
      className={className}
      width={1920}
      height={1080}
    />
  )
}
```

### Image CDN Transformations

```ts
// Transformation reference
const url = imageUrl(source)
  .width(800)                     // Resize width
  .height(600)                    // Resize height
  .format('webp')                 // Auto-convert to WebP
  .quality(80)                    // Compression quality 1-100
  .fit('clip')                    // clip|crop|fill|fillmax|max|min|scale
  .crop('center')                 // Crop from center (or focal point)
  .blur(10)                       // Blur effect
  .sharpen(20)                    // Sharpen effect 0-100
  .brightness(10)                 // Adjust brightness -100 to 100
  .saturation(10)                 // Adjust saturation -100 to 100
  .orientation(90)                // Rotate 0, 90, 180, 270
  .dpr(2)                         // Device pixel ratio
  .url()
```

### Hotspot & Crop

```ts
// Access hotspot data from schema
defineField({
  name: 'image',
  type: 'image',
  options: {
    hotspot: true, // Enables hotspot + crop UI in Studio
  },
})

// GROQ: fetch hotspot data
const query = `*[_type == "post"]{
  "image": coverImage{
    asset->{_id, url, metadata {dimensions, lqip}},
    crop,
    hotspot
  }
}`
```

### SVG Handling

```ts
// Sanity doesn't support SVG natively. Store as file:
defineField({
  name: 'svgFile',
  type: 'file',
  options: {
    accept: '.svg',
  },
  fields: [
    { name: 'alt', type: 'string', title: 'Description' },
  ],
})

// Render SVG inline via fetch
export async function InlineSVG({ assetId }: { assetId: string }) {
  const url = client.getDocument(assetId)?.url
  if (!url) return null
  const svgContent = await fetch(url).then((r) => r.text())
  return <div dangerouslySetInnerHTML={{ __html: svgContent }} />
}
```

### Video Assets with Mux

```ts
// sanity.config.ts
import { muxInput } from '@sanity/mux-input'

export default defineConfig({
  plugins: [muxInput()],
})

// Schema field
defineField({
  name: 'video',
  title: 'Video',
  type: 'mux.video',
})

// GROQ query for video
const query = `
*[_type == "post" && slug.current == $slug][0]{
  "video": video->{playbackId, assetId, data{...}}
}
`

// React component
import MuxPlayer from '@mux/mux-player-react'

export function VideoPlayer({ playbackId }: { playbackId: string }) {
  return (
    <MuxPlayer
      streamType="on-demand"
      playbackId={playbackId}
      accentColor="#c96442"
    />
  )
}
```

---

## 8. Performance & Caching

### CDN Caching Strategy

```ts
// lib/sanity/client.ts
export const client = createClient({
  projectId,
  dataset,
  apiVersion,
  useCdn: process.env.NODE_ENV === 'production', // CDN in prod, direct in dev
  perspective: 'published',
})

// Override per-query
await client.fetch(query, params, {
  useCdn: false,  // Skip CDN for freshness
  cache: 'force-cache',  // Force caching
  next: { revalidate: 60 },
})
```

### GROQ Query Optimization

```groq
// BAD — unindexed field filter causes full scan
*[_type == "post" && someArbitraryField == "value"]

// GOOD — filter on indexed fields (_type, _id, _updatedAt, slug, references)
*[_type == "post" && slug.current == "my-slug"]

// BAD — fetching entire documents
*[_type == "post"]

// GOOD — projection with only needed fields
*[_type == "post"]{title, slug, excerpt, publishedAt}

// BAD — deep joins on large datasets without limits
*[_type == "post"]{author->{name, image, department->name}}

// GOOD — limit depth, use projections
*[_type == "post"]{title, "author": author->name}
```

### Persisted Queries

```ts
// lib/sanity/persistedQueries.ts
import { client } from './client'

const QUERIES = {
  siteSettings: groq`*[_type == "siteSettings"][0]{title, description, "navItems": navItems[]->{title, slug}}`,
  posts: groq`*[_type == "post"] | order(publishedAt desc) [0..19]{title, slug, excerpt, publishedAt, "author": author->name}`,
  postBySlug: groq`*[_type == "post" && slug.current == $slug][0]{title, body, publishedAt, "author": author->name}`,
} as const

export async function getPersisted<T extends keyof typeof QUERIES>(
  key: T,
  params?: Record<string, unknown>
): Promise<ReturnType<typeof QUERIES[T]>> {
  return client.fetch(QUERIES[key], params || {})
}
```

### Cache Headers & Revalidation

```ts
// Route segment config for pages
export const revalidate = 60 // ISR fallback

// Per-fetch cache control
const data = await client.fetch(query, params, {
  next: {
    tags: ['posts', 'authors'],
    revalidate: 300,
  },
})

// On-demand revalidation in webhook
export async function POST(req: NextRequest) {
  const { _type, _id } = await req.json()
  revalidateTag(_type)
  revalidateTag(`${_type}:${_id}`)
  return NextResponse.json({ revalidated: true })
}
```

### Bundle Size Optimization — Studio

```ts
// sanity.config.ts
import { defineConfig } from 'sanity'

export default defineConfig({
  // ...
  __dangerous_takeover: {
    lazyLoadPlugins: true, // Load plugins only when needed
  },
  plugins: [
    // Use environment-specific plugins
    ...(process.env.NODE_ENV === 'development'
      ? [structureTool(), visionTool()]
      : [structureTool()]),
  ].filter(Boolean),
})
```

### Sanity Listener for Real-Time Updates

```ts
// hooks/useSanityListener.ts
import { useEffect, useState } from 'react'
import { client } from '@/lib/sanity/client'
import type { SanityDocument } from '@sanity/client'

export function useSanityListener(query: string, params?: Record<string, unknown>) {
  const [data, setData] = useState<SanityDocument | null>(null)

  useEffect(() => {
    const subscription = client.listen(query, params).subscribe((update) => {
      if (update.result) {
        setData(update.result as SanityDocument)
      }
    })

    return () => subscription.unsubscribe()
  }, [query, JSON.stringify(params)])

  return data
}
```

---

## 9. GROQ Query Patterns (Real Examples)

### Blog — Posts with Author, Categories, Pagination

```groq
// Blog listing — page 1 of 20
{
  "total": count(*[_type == "post"]),
  "posts": *[_type == "post"]
    | order(publishedAt desc)
    [0..19]{
      title,
      "slug": slug.current,
      "author": author->{name, "avatar": image.asset->url},
      "categories": categories[]->{title, "slug": slug.current},
      excerpt,
      publishedAt,
      "coverImage": coverImage{
        asset->{_id, url, metadata {lqip, dimensions}},
        alt
      }
    }
}

// Single post with adjacent posts
{
  "post": *[_type == "post" && slug.current == $slug][0]{
    ...,
    "author": author->{name, "avatar": image.asset->url},
    "categories": categories[]->{title, slug},
    "plainBody": pt::text(body)
  },
  "prev": *[_type == "post" && publishedAt < ^.post.publishedAt]
    | order(publishedAt desc) [0]{title, "slug": slug.current},
  "next": *[_type == "post" && publishedAt > ^.post.publishedAt]
    | order(publishedAt asc) [0]{title, "slug": slug.current}
}

// Posts by category
*[_type == "post" && references($categoryId)]
  | order(publishedAt desc)
  [0..9]{
    title, slug, excerpt, publishedAt
  }

// Related posts (same categories)
*[_type == "post"
  && _id != $postId
  && count(categories[@._ref in $categoryIds]) > 0
] | order(publishedAt desc) [0..3]{title, slug}
```

### E-Commerce — Products with Variants

```groq
// Product listing with variants
*[_type == "product"]{
  name,
  slug,
  "defaultPrice": variants[0].price,
  "defaultImage": images[0]{asset->{url, metadata}},
  "inStock": variants[].inStock match true
}

// Product detail with variant selection
*[_type == "product" && slug.current == $slug][0]{
  name,
  description,
  "images": images[]{asset->{url, metadata {lqip, dimensions}}, alt},
  variants[]{
    sku,
    name,
    price,
    compareAt,
    inStock,
    attributes
  },
  "category": category->{name, slug},
  "relatedProducts": *[_type == "product" && references(^._id)] | order(_createdAt desc) [0..4]{
    name, slug, "price": variants[0].price
  }
}

// Inventory status aggregation
{
  "totalProducts": count(*[_type == "product"]),
  "inStock": count(*[_type == "product" && variants[].inStock match true]),
  "outOfStock": count(*[_type == "product" && !(variants[].inStock match true)]),
  "byCategory": *[_type == "category"]{
    name,
    "count": count(*[_type == "product" && references(^._id)]),
    "avgPrice": avg(*[_type == "product" && references(^._id)].variants[0].price)
  }
}
```

### Portfolios — Projects with Tags

```groq
// Portfolio with tag filtering
*[_type == "project" && (!defined($tag) || $tag in tags[]->slug.current)]
  | order(featured desc, completedAt desc)
  [0..11]{
    title,
    "slug": slug.current,
    "thumbnail": thumbnail{asset->{url, metadata}, alt},
    tags[]->{name, slug},
    "summary": pt::text(description)[0..200],
    category->{name}
  }

// Single project
*[_type == "project" && slug.current == $slug][0]{
  title,
  description,
  "gallery": gallery[]{asset->{url, metadata}, alt, caption},
  tags[]->{name, slug},
  completedAt,
  client,
  url,
  category->name
}

// Tag cloud with counts
*[_type == "tag"]{
  name,
  slug,
  "count": count(*[_type == "project" && references(^._id)])
}
```

### Landing Page Builder — Modular Sections

```groq
// Page with modular content sections
*[_type == "landingPage" && slug.current == $slug][0]{
  title,
  seo,
  "sections": sections[]{
    _type == "hero" => {
      _type,
      heading,
      subheading,
      "background": background{asset->{url}},
      cta
    },
    _type == "features" => {
      _type,
      title,
      features[]{
        icon,
        title,
        description
      }
    },
    _type == "testimonials" => {
      _type,
      title,
      "testimonials": testimonials[]->{
        name,
        role,
        quote,
        "avatar": avatar{asset->{url}}
      }
    },
    _type == "cta" => {
      _type,
      heading,
      buttonText,
      buttonUrl
    }
  }
}
```

### Site Settings — SEO, Navigation, Footer

```groq
// Full site settings with navigation
*[_type == "siteSettings"][0]{
  title,
  description,
  "logo": logo{asset->{url, metadata}, alt},
  favicon,
  "mainNav": mainNav[]{
    ...,
    _type == "navLink" => {
      label,
      "url": select(
        defined(internal) => internal->slug.current,
        external
      ),
      "isExternal": defined(external)
    },
    _type == "navDropdown" => {
      label,
      "children": children[]{
        label,
        "url": select(
          defined(internal) => internal->slug.current,
          external
        )
      }
    }
  },
  "footer": footer{
    description,
    "socialLinks": socialLinks[]{platform, url},
    "quickLinks": quickLinks[]{label, "url": link->slug.current},
    copyright
  },
  seo{
    defaultTitle,
    titleTemplate,
    defaultDescription,
    "ogImage": ogImage{asset->{url}},
    twitterHandle
  }
}
```

### Search Across Multiple Document Types

```groq
// Unified search
{
  "posts": *[_type == "post" && title match $searchTerm + "*"] | order(publishedAt desc) [0..4]{
    _type,
    title,
    "slug": slug.current,
    publishedAt,
    "match": "title"
  },
  "pages": *[_type == "page" && title match $searchTerm + "*"] [0..4]{
    _type,
    title,
    "slug": slug.current,
    "match": "title"
  },
  "products": *[_type == "product" && name match $searchTerm + "*"] [0..4]{
    _type,
    name,
    "slug": slug.current,
    "match": "name"
  }
}

// Full-text search (GROQ doesn't have native full-text — workaround)
*[_type in ["post", "page", "product"] &&
  title match $searchTerm + "*" ||
  defined(description) && pt::text(description) match $searchTerm
] | order(_score desc){
  _type,
  "title": select(
    _type == "product" => name,
    title
  ),
  "slug": slug.current,
  "excerpt": defined(description) ? pt::text(description)[0..200] : ""
}[0..20]
```

---

## 10. TypeScript Integration

### Generate Types from Schema

```bash
# Install
npm install -D @sanity/codegen

# Configure sanity.codegen.ts
```

```ts
// sanity.codegen.ts
import type { SanityCodegenConfig } from '@sanity/codegen'

const config: SanityCodegenConfig = {
  schemaPath: './schemas/**/*.ts',
  outputPath: './types/sanity.ts',
}

export default config
```

```bash
# Generate types
npx sanity-codegen
```

### Generated Types (Output)

```ts
// types/sanity.ts (auto-generated)
export interface SanityImage {
  _type: 'image'
  asset: SanityReference<SanityImageAsset>
  hotspot?: { x: number; y: number; width: number; height: number }
  crop?: { top: number; bottom: number; left: number; right: number }
  alt?: string
}

export interface Post {
  _id: string
  _type: 'post'
  _createdAt: string
  _updatedAt: string
  _rev: string
  title?: string
  slug?: { _type: 'slug'; current: string }
  author?: SanityReference<Author>
  categories?: Array<SanityReference<Category>>
  publishedAt?: string
  excerpt?: string
  coverImage?: SanityImage
  body?: PortableTextBlock[]
  seo?: SeoMeta
  featured?: boolean
}

export type PortableTextBlock = {
  _type: 'block'
  _key: string
  children: PortableTextSpan[]
  markDefs?: PortableTextMarkDef[]
  style?: 'normal' | 'h1' | 'h2' | 'h3' | 'h4' | 'blockquote'
  listItem?: 'bullet' | 'number'
  level?: number
}
```

### Typed GROQ Queries

```ts
// lib/sanity/queries.ts
import { groq } from 'next-sanity'
import type { Post, Author } from '@/types/sanity'

// Typed query result
export const postsQuery = groq`*[_type == "post"] | order(publishedAt desc) [0..19]{
  _id,
  title,
  "slug": slug.current,
  publishedAt,
  excerpt,
  "author": author->name
}`

export type PostsListResult = Array<{
  _id: string
  title: string | null
  slug: string | null
  publishedAt: string | null
  excerpt: string | null
  author: string | null
}>

// Single post with full detail
export const postQuery = groq`*[_type == "post" && slug.current == $slug][0]{
  ...,
  "author": author->{name, image},
  "categories": categories[]->{title, slug}
}`

export type PostResult = Post & {
  author: { name: string; image: SanityImage } | null
  categories: Array<{ title: string; slug: { current: string } }> | null
}
```

### Typed Client Fetch

```ts
// lib/sanity/typedFetch.ts
import { client } from './client'
import type { QueryParams } from '@sanity/client'

export async function typedFetch<T>(
  query: string,
  params?: QueryParams,
  options?: { tags?: string[]; revalidate?: number }
): Promise<T> {
  return client.fetch<T>(query, params, {
    next: { tags: options?.tags, ...(options?.revalidate && { revalidate: options.revalidate }) },
  })
}

// Usage with full type safety
const posts = await typedFetch<PostsListResult>(postsQuery, {}, { tags: ['post'] })
const post = await typedFetch<PostResult>(postQuery, { slug: 'hello-world' })
```

### Type-Safe Image URLs

```ts
// lib/sanity/image.ts
import imageUrlBuilder from '@sanity/image-url'
import { client } from './client'
import type { SanityImageSource } from '@sanity/image-url/lib/types/types'

const builder = imageUrlBuilder(client)

interface ImageOptions {
  width?: number
  height?: number
  format?: 'webp' | 'jpg' | 'png' | 'avif'
  quality?: number
  fit?: 'clip' | 'crop' | 'fill' | 'fillmax' | 'max' | 'min' | 'scale'
  blur?: number
  sharpen?: number
  dpr?: number
}

export function getSanityImageUrl(
  source: SanityImageSource | undefined | null,
  options: ImageOptions = {}
): string | undefined {
  if (!source) return undefined

  let url = builder.image(source)

  if (options.width) url = url.width(options.width)
  if (options.height) url = url.height(options.height)
  if (options.format) url = url.format(options.format)
  if (options.quality) url = url.quality(options.quality)
  if (options.fit) url = url.fit(options.fit)
  if (options.blur) url = url.blur(options.blur)
  if (options.sharpen) url = url.sharpen(options.sharpen)
  if (options.dpr) url = url.dpr(options.dpr)

  return url.url()
}
```

### Type-Safe Preview Props

```ts
// types/preview.ts
import type { SanityDocument } from '@sanity/client'

export interface PreviewProps<T extends SanityDocument = SanityDocument> {
  document: T
  draft: T | null
  published: T | null
  isPreview: boolean
}

// Component with typed preview
export function PostPreview({ document, draft }: PreviewProps<Post>) {
  const post = draft || document
  return (
    <article>
      <h1>{post.title}</h1>
      <p>{post.excerpt}</p>
    </article>
  )
}
```

---

## 11. File Convention

```
project/
├── sanity.config.ts            # Main config: plugins, theme, dataset
├── sanity.cli.ts               # CLI config: project ID, dataset
├── sanity.codegen.ts           # Type codegen config
├── schemas/
│   ├── index.ts                # Exports all schemas
│   ├── post.ts                 # Document types
│   ├── page.ts
│   ├── product.ts
│   ├── author.ts
│   ├── category.ts
│   ├── singletons/
│   │   └── siteSettings.ts     # Singleton document
│   ├── blocks/
│   │   ├── blockContent.ts     # Portable Text config
│   │   ├── imageBlock.ts       # Image with caption block
│   │   ├── codeBlock.ts        # Code snippet block
│   │   └── callout.ts          # Callout/alert block
│   ├── objects/
│   │   ├── localeString.ts     # i18n field group
│   │   ├── localeBlock.ts      # i18n portable text
│   │   ├── seoMeta.ts          # SEO metadata object
│   │   ├── link.ts             # Link object
│   │   └── color.ts            # Color picker object
│   └── components/
│       └── SlugInput.tsx       # Custom input component
├── studio/
│   ├── structure.ts            # Desk structure builder
│   ├── components/
│   │   ├── PostPreview.tsx     # Custom preview in CMS
│   │   ├── Navbar.tsx          # Custom navbar
│   │   └── Logo.tsx            # Custom logo
│   ├── actions/
│   │   └── workflowActions.ts  # Custom document actions
│   └── tools/
│       └── importTool.tsx      # Custom tool
├── plugins/
│   └── dashboard/
│       └── index.ts            # Custom plugin
├── types/
│   ├── sanity.ts               # Generated types
│   └── groq.ts                 # Typed query results
├── lib/
│   ├── sanity/
│   │   ├── client.ts           # Sanity client
│   │   ├── fetch.ts            # Typed fetch helper
│   │   ├── image.ts            # Image URL builder
│   │   └── queries.ts          # GROQ query constants
│   └── env.ts                  # Environment variables
└── app/
    └── api/
        ├── draft/route.ts      # Next.js draft mode
        └── revalidate/route.ts # Webhook revalidation
```

---

## 12. Anti-Patterns (with Fixes)

### AP-1: Fetching Entire Documents

```groq
// BAD — fetches ALL fields including heavy body content
*[_type == "post"]{...}

// GOOD — projection with only needed fields
*[_type == "post"]{title, slug, excerpt, publishedAt}
```

### AP-2: Deeply Nested Arrays

```ts
// BAD — inline nested array that will bloat document size
defineField({
  name: 'orderItems',
  type: 'array',
  of: [{
    type: 'object',
    fields: [
      { name: 'product', type: 'string' },
      { name: 'quantity', type: 'number' },
      { name: 'price', type: 'number' },
      { name: 'notes', type: 'text' },
    ],
  }],
})

// GOOD — reference to order item documents
defineField({
  name: 'orderItems',
  type: 'array',
  of: [{ type: 'reference', to: [{ type: 'orderItem' }] }],
})

// Or flatten arrays into dedicated document type for pagination
```

### AP-3: Using Block Content for Everything

```ts
// BAD — block content for structured data
defineField({
  name: 'faq',
  type: 'blockContent', // Wrong! Block content is for prose, not structured Q&A
})

// GOOD — dedicated object type
defineField({
  name: 'faqs',
  type: 'array',
  of: [{
    type: 'object',
    fields: [
      { name: 'question', type: 'string' },
      { name: 'answer', type: 'text' },
    ],
    preview: {
      select: { title: 'question' },
    },
  }],
})
```

### AP-4: Not Using CDN

```ts
// BAD — direct API in production (no cache)
const client = createClient({
  projectId,
  dataset,
  apiVersion,
  useCdn: false, // Always hits the API, not CDN
})

// GOOD — CDN in production
const client = createClient({
  projectId,
  dataset,
  apiVersion,
  useCdn: process.env.NODE_ENV === 'production',
})
```

### AP-5: Over-fetching in GROQ

```groq
// BAD — fetching entire document just for one field
const slugs = await client.fetch(`*[_type == "post"]{...}`)
const slugsOnly = slugs.map((p) => p.slug.current)

// GOOD — fetch only what you need
const slugs = await client.fetch(`*[_type == "post"]{"slug": slug.current}`)
```

### AP-6: No Draft Mode Handling

```ts
// BAD — same query for preview and production
export async function getPost(slug: string) {
  return client.fetch(query, { slug })
}

// GOOD — conditional perspective
export async function getPost(slug: string, preview = false) {
  return client.fetch(query, { slug }, {
    perspective: preview ? 'previewDrafts' : 'published',
    useCdn: !preview,
  })
}
```

### AP-7: Missing GROQ Projections on References

```groq
// BAD — returns full referenced document
*[_type == "post"]{author->}

// GOOD — selective projection
*[_type == "post"]{author->{name, image}}
```

### AP-8: Not Using `defined()` Guard

```groq
// BAD — filter fails on null/undefined fields
*[_type == "post" && publishedAt > $date]

// GOOD — guard against missing fields
*[_type == "post" && defined(publishedAt) && publishedAt > $date]
```

### AP-9: Large Document Validation in Studio

```ts
// BAD — expensive validation runs on every keystroke
defineField({
  name: 'body',
  type: 'blockContent',
  validation: (rule) => rule.custom((value) => {
    const totalChars = value.reduce((acc, block) => acc + JSON.stringify(block).length, 0)
    return totalChars < 100000 || 'Too large'
  }),
})

// GOOD — use custom input component for expensive checks
```

### AP-10: No Type Safety

```ts
// BAD — query results are 'any'
const data = await client.fetch(query)

// GOOD — typed results
const data = await client.fetch<PostResult>(query)
```

---

## 13. Implementation Checklist

### Schema & Content Modeling
- [ ] Define all document types with proper validation
- [ ] Create reusable object types for common patterns
- [ ] Implement singleton pattern for site settings
- [ ] Set up block content with custom block types
- [ ] Configure field groups for complex schemas
- [ ] Add preview configurations for each document
- [ ] Set up initial values where appropriate
- [ ] Implement ordering on relevant types

### Studio Configuration
- [ ] Customize desk structure with logical grouping
- [ ] Add custom document lists with filters
- [ ] Implement custom preview components
- [ ] Theme the studio with brand colors
- [ ] Configure role-based access control
- [ ] Install and configure essential plugins
- [ ] Add custom document actions for workflow
- [ ] Set up production URL for preview

### GROQ Queries
- [ ] Optimize all queries with projections
- [ ] Use parameterized queries for dynamic data
- [ ] Implement pagination with `[offset...limit]`
- [ ] Add `defined()` guards to date filters
- [ ] Use `coalesce()` for fallback values
- [ ] Implement search across document types
- [ ] Add subqueries for aggregated data

### Next.js Integration
- [ ] Set up `next-sanity` client with CDN
- [ ] Implement typed fetch helper with draft mode
- [ ] Add static generation with GROQ
- [ ] Configure ISR with cache tags
- [ ] Set up Next.js draft mode route handler
- [ ] Implement webhook revalidation endpoint
- [ ] Add real-time preview with `useLiveQuery`
- [ ] Create responsive image component

### Internationalization
- [ ] Install and configure i18n plugin
- [ ] Choose document-level vs field-level strategy
- [ ] Create locale field types (localeString, localeBlock)
- [ ] Write GROQ queries with fallback
- [ ] Add language switcher in frontend

### Performance
- [ ] Enable CDN caching in production
- [ ] Optimize all GROQ queries (filter order, projections)
- [ ] Implement ISR with cache tags
- [ ] Configure proper cache headers
- [ ] Set up Sanity listeners only when needed
- [ ] Lazy load studio plugins in production
- [ ] Use persisted queries for stable data

### TypeScript
- [ ] Run `sanity-codegen` for type generation
- [ ] Create typed query result interfaces
- [ ] Add type-safe fetch wrapper
- [ ] Implement type-safe image URL builder
- [ ] Add typed preview props

### Deployment
- [ ] Add environment variables for all environments
- [ ] Configure webhook in Sanity project
- [ ] Set up revalidation on production
- [ ] Test draft mode end-to-end
- [ ] Verify CDN caching is working
- [ ] Monitor query performance

---

## 14. Common Troubleshooting

### "GROQ query returns empty array but document exists"
- Check perspective: `previewDrafts` vs `published`
- Verify the field filter is indexed (slug, _id)
- Use `defined(slug.current)` guard
- Check for draft versions in the dataset

### "useLiveQuery doesn't update"
- Ensure `@sanity/preview-kit` is installed
- Check that stega is enabled: `stega: true`
- Verify the client is in preview mode
- Check network tab for listener connections

### "Sanity Studio is slow"
- Remove unused plugins
- Lazy load heavy plugins
- Check for custom components causing re-renders
- Use field groups to split large schemas
- Reduce number of document list items

### "Image transformations are not working"
- Check hotspot: `options: { hotspot: true }`
- Verify image asset is fully uploaded
- Use correct image URL builder format
- Check CDN URL for proper parameters

### "Cross-dataset references failing"
- Dataset must be in the same project
- Configure `studioUrl` for reference resolution
- Verify both datasets exist
- Check ACL permissions across datasets

### "Webhook revalidation not triggering"
- Verify webhook URL is publicly accessible
- Check signature validation logic
- Ensure tags match between fetch and revalidate
- Check server logs for webhook requests

### "TypeScript types mismatch"
- Regenerate types with `npx sanity-codegen`
- Verify schema path in codegen config
- Check for duplicate type names
- Ensure all schema files are included

### "Preview not loading in Studio"
- Configure `productionUrl` in sanity.config.ts
- Verify the preview route handler works
- Check that preview secret matches
- Ensure the document has a slug

### "CDN returning stale data"
- Check `useCdn` is false in preview
- Verify cache tags are set correctly
- Wait for CDN propagation (up to 5 min)
- Use `perspective: 'published'` + `useCdn: false` for fresh data

### "GROQ query timeout"
- Add explicit filters to reduce scan range
- Limit results before ordering
- Use projections instead of `{...}`
- Avoid deep joins on large datasets
- Consider pagination for large result sets

### "Portable Text rendering broken"
- Import `@portabletext/react` for React rendering
- Define custom serializers for all block types
- Handle marks/annotations properly
- Check for missing `_key` values on blocks

### "Duplicate slug errors in Studio"
- Add `slug` validation for uniqueness
- Use custom validation function to check existing slugs
- Consider using `slugify` with suffix for duplicates
- Implement prefix-based slug strategy (_type + title)
