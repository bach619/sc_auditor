---
name: backend-nodejs
description: Node.js backend mastery: Express.js, Fastify, Nest.js, async/await patterns, error handling, middleware architecture, database integration, testing, security, and production deployment
license: MIT
compatibility: opencode
metadata:
  audience: backend-developers
  domain: backend
  paradigm: event-driven
  capabilities:
    - express-patterns
    - fastify-patterns
    - nestjs-patterns
    - middleware-architecture
    - error-handling
    - database-integration
    - authentication
    - testing-strategy
    - performance-optimization
    - security-hardening
    - api-design
    - websocket-patterns
    - background-jobs
    - logging-observability
  integrates_with:
    - database-postgres
    - database-event-sourcing
    - devops-platform-engineering
    - security-audit
---

## Backend Node.js Skill

### Core Patterns

#### Framework Decision Tree

```
Which Node.js framework should I use?
                    │
                    ▼
      ┌─────────────┴─────────────┐
      │                           │
   Is the team experienced       Do you need
   with TypeScript + DI?         maximum throughput
      │                           (req/s)?
      │                           │
     YES            NO            │
      │              │            │
      ▼              ▼            │
   Nest.js        Is the API     │
   (Module/         simple       │
   Controller/      CRUD +       │
   Service/         some          │
   Decorator)      middleware?    │
                     │            │
                    YES           │
                     │            │
                     ▼            │
                  Express.js      │
                   (minimal,      │
                    flexible)     │
                                  │
                                  │
                                  ▼
                               Fastify
                              (fastest,
                               schema-based,
                               serialization)
```

#### Express.js — Application Factory Pattern

```ts
// src/app.ts
import express, { type Express, type Request, type Response, type NextFunction } from 'express'
import cors from 'cors'
import helmet from 'helmet'
import { errorHandler } from './middleware/error-handler'
import { requestLogger } from './middleware/request-logger'
import { requestId } from './middleware/request-id'
import { userRouter } from './routes/users'
import { healthRouter } from './routes/health'

export function createApp(): Express {
  const app = express()

  // Global middleware — order matters
  app.use(helmet())
  app.use(cors())
  app.use(express.json({ limit: '10kb' }))
  app.use(requestId)
  app.use(requestLogger)

  // Routes
  app.use('/api/v1/health', healthRouter)
  app.use('/api/v1/users', userRouter)

  // 404 handler
  app.use((_req: Request, res: Response) => {
    res.status(404).json({ success: false, error: { code: 'NOT_FOUND', message: 'Route not found' } })
  })

  // Global error handler (4 params = Express error middleware)
  app.use(errorHandler)

  return app
}
```

```ts
// src/server.ts
import { createApp } from './app'
import { logger } from './lib/logger'

const PORT = process.env.PORT ?? 3000
const app = createApp()

const server = app.listen(PORT, () => {
  logger.info({ port: PORT }, 'Server started')
})

// Graceful shutdown
function shutdown(signal: string) {
  return async () => {
    logger.info({ signal }, 'Shutdown signal received')
    server.close(() => {
      logger.info('HTTP server closed')
      process.exit(0)
    })
    // Force exit after 10s
    setTimeout(() => process.exit(1), 10_000).unref()
  }
}

process.on('SIGTERM', shutdown('SIGTERM'))
process.on('SIGINT', shutdown('SIGINT'))
process.on('unhandledRejection', (reason) => {
  logger.error({ err: reason }, 'Unhandled Rejection')
})
process.on('uncaughtException', (err) => {
  logger.error({ err }, 'Uncaught Exception')
  process.exit(1)
})
```

#### Fastify — Schema-Based Routing

```ts
// src/app.ts
import Fastify from 'fastify'
import cors from '@fastify/cors'
import helmet from '@fastify/helmet'
import { userRoutes } from './routes/users'
import { errorHandler } from './hooks/error-handler'

export async function buildApp() {
  const app = Fastify({
    logger: true,
    bodyLimit: 10_240,
  })

  await app.register(cors, { origin: process.env.CORS_ORIGIN })
  await app.register(helmet)

  app.setErrorHandler(errorHandler)

  await app.register(userRoutes, { prefix: '/api/v1/users' })

  return app
}
```

```ts
// src/routes/users.ts
import type { FastifyInstance } from 'fastify'
import { z } from 'zod'

const CreateUserSchema = {
  body: z.object({
    name: z.string().min(1).max(100),
    email: z.string().email(),
  }),
  response: {
    201: z.object({
      success: z.literal(true),
      data: z.object({ id: z.string(), name: z.string(), email: z.string() }),
    }),
    409: z.object({ success: z.literal(false), error: z.object({ code: z.string(), message: z.string() }) }),
  },
}

export async function userRoutes(app: FastifyInstance) {
  app.post<{ Body: z.infer<typeof CreateUserSchema.body> }>('/', {
    schema: {
      body: CreateUserSchema.body,
      response: CreateUserSchema.response,
    },
  }, async (request, reply) => {
    const { name, email } = request.body
    const user = await createUser(name, email)
    return reply.status(201).send({ success: true, data: user })
  })

  app.get('/:id', async (request, reply) => {
    // Fastify serialization based on response schema or manual
    const user = await findUserById(request.params.id)
    if (!user) {
      return reply.status(404).send({
        success: false,
        error: { code: 'NOT_FOUND', message: 'User not found' },
      })
    }
    return { success: true, data: user }
  })
}
```

#### Nest.js — Module/Controller/Service/Decorator

```ts
// src/users/users.module.ts
import { Module } from '@nestjs/common'
import { UsersController } from './users.controller'
import { UsersService } from './users.service'
import { PrismaModule } from '../prisma/prisma.module'

@Module({
  imports: [PrismaModule],
  controllers: [UsersController],
  providers: [UsersService],
  exports: [UsersService],
})
export class UsersModule {}
```

```ts
// src/users/users.controller.ts
import { Controller, Get, Post, Body, Param, ParseUUIDPipe, UseGuards } from '@nestjs/common'
import { UsersService } from './users.service'
import { CreateUserDto } from './dto/create-user.dto'
import { JwtAuthGuard } from '../auth/guards/jwt-auth.guard'

@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Post()
  async create(@Body() dto: CreateUserDto) {
    return this.usersService.create(dto)
  }

  @UseGuards(JwtAuthGuard)
  @Get(':id')
  async findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.findById(id)
  }
}
```

```ts
// src/users/users.service.ts
import { Injectable, NotFoundException } from '@nestjs/common'
import { PrismaService } from '../prisma/prisma.service'
import { CreateUserDto } from './dto/create-user.dto'

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async create(dto: CreateUserDto) {
    return this.prisma.user.create({ data: dto })
  }

  async findById(id: string) {
    const user = await this.prisma.user.findUnique({ where: { id } })
    if (!user) throw new NotFoundException('User not found')
    return user
  }
}
```

---

### Middleware Architecture

#### Middleware Chain Pattern

```
Request
  │
  ▼
┌─────────────────────────────────────────────────┐
│           GLOBAL MIDDLEWARE STACK                │
│                                                   │
│  helmet → cors → json parser → requestId →        │
│  requestLogger → rateLimiter → auth               │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           ROUTER MIDDLEWARE STACK                │
│                                                   │
│  validateBody → authorize → [ROUTE HANDLER]      │
└─────────────────────┬───────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│           ERROR HANDLER STACK                    │
│                                                   │
│  [AppError] → NotFound → [Error Response]        │
└─────────────────────────────────────────────────┘
                      │
                      ▼
                   Response
```

#### Express Middleware Types

```ts
// Application-level middleware — runs on ALL routes
app.use(helmet())
app.use(cors())

// Router-level middleware — runs only on this router
const router = express.Router()
router.use(authMiddleware)
router.use(rateLimiter)

// Route-level middleware — runs only on this specific route
router.get('/profile', validateSession, getProfile)

// Error middleware — MUST have 4 parameters
function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction) {
  // handle error
}
```

#### Custom Middleware Examples

```ts
// src/middleware/request-id.ts
import { randomUUID } from 'node:crypto'
import type { Request, Response, NextFunction } from 'express'

declare global {
  namespace Express {
    interface Request {
      requestId: string
    }
  }
}

export function requestId(req: Request, _res: Response, next: NextFunction) {
  req.requestId = (req.headers['x-request-id'] as string) ?? randomUUID()
  next()
}
```

```ts
// src/middleware/latency-tracker.ts
import type { Request, Response, NextFunction } from 'express'
import { logger } from '../lib/logger'

export function latencyTracker(req: Request, res: Response, next: NextFunction) {
  const start = performance.now()

  res.on('finish', () => {
    const duration = performance.now() - start
    logger.info({
      method: req.method,
      path: req.path,
      status: res.statusCode,
      duration: `${duration.toFixed(2)}ms`,
      requestId: req.requestId,
    })
  })

  next()
}
```

#### Fastify Hooks

```ts
// preHandler — runs before route handler
app.addHook('preHandler', async (request) => {
  // Runs after validation, before handler
  const token = request.headers.authorization
  if (token) {
    request.user = await verifyToken(token)
  }
})

// preValidation — runs before schema validation
app.addHook('preValidation', async (request) => {
  // Modify input before validation (e.g., trim strings)
})

// onSend — runs before response is sent
app.addHook('onSend', async (request, reply, payload) => {
  // Transform response payload
  return payload
})

// onResponse — runs after response is sent (logging)
app.addHook('onResponse', async (request, reply) => {
  request.log.info({ url: request.url, status: reply.statusCode }, 'request completed')
})
```

#### Nest.js Guards, Interceptors, Pipes, Filters

```ts
// Guard — determines if request can proceed (auth)
// src/auth/guards/roles.guard.ts
import { Injectable, CanActivate, ExecutionContext } from '@nestjs/common'
import { Reflector } from '@nestjs/core'
import { ROLES_KEY } from '../decorators/roles.decorator'

@Injectable()
export class RolesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredRoles = this.reflector.getAllAndOverride<string[]>(ROLES_KEY, [
      context.getHandler(),
      context.getClass(),
    ])
    if (!requiredRoles) return true
    const { user } = context.switchToHttp().getRequest()
    return requiredRoles.includes(user.role)
  }
}

// Interceptor — transforms response / runs logic around handler
// src/common/interceptors/transform.interceptor.ts
import { Injectable, NestInterceptor, ExecutionContext, CallHandler } from '@nestjs/common'
import { Observable } from 'rxjs'
import { map } from 'rxjs/operators'

export interface ApiResponse<T> {
  success: boolean
  data: T
  timestamp: string
}

@Injectable()
export class TransformInterceptor<T> implements NestInterceptor<T, ApiResponse<T>> {
  intercept(context: ExecutionContext, next: CallHandler): Observable<ApiResponse<T>> {
    return next.handle().pipe(
      map(data => ({
        success: true,
        data,
        timestamp: new Date().toISOString(),
      })),
    )
  }
}

// Pipe — transforms/validates input
// src/common/pipes/parse-positive-int.pipe.ts
import { PipeTransform, Injectable, BadRequestException } from '@nestjs/common'

@Injectable()
export class ParsePositiveIntPipe implements PipeTransform<string, number> {
  transform(value: string): number {
    const val = parseInt(value, 10)
    if (isNaN(val) || val < 1) {
      throw new BadRequestException('Validation failed: positive integer expected')
    }
    return val
  }
}

// Exception filter — catches thrown exceptions
// src/common/filters/http-exception.filter.ts
import { ExceptionFilter, Catch, ArgumentsHost, HttpException } from '@nestjs/common'
import type { Response } from 'express'

@Catch(HttpException)
export class HttpExceptionFilter implements ExceptionFilter {
  catch(exception: HttpException, host: ArgumentsHost) {
    const ctx = host.switchToHttp()
    const response = ctx.getResponse<Response>()
    const status = exception.getStatus()
    const exceptionResponse = exception.getResponse()

    response.status(status).json({
      success: false,
      error: {
        code: exception.name,
        message: typeof exceptionResponse === 'string' ? exceptionResponse : (exceptionResponse as any).message,
        timestamp: new Date().toISOString(),
      },
    })
  }
}
```

#### Rate Limiting, Compression, CORS

```ts
// Express
import rateLimit from 'express-rate-limit'
import compression from 'compression'

// Global rate limit
app.use(rateLimit({
  windowMs: 15 * 60 * 1000,  // 15 minutes
  max: 100,                    // limit each IP to 100 requests per window
  standardHeaders: true,
  legacyHeaders: false,
  message: { success: false, error: { code: 'RATE_LIMIT', message: 'Too many requests' } },
}))

// Per-route rate limit (stricter for auth endpoints)
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5,
  message: { success: false, error: { code: 'RATE_LIMIT', message: 'Too many auth attempts' } },
})
app.use('/api/v1/auth', authLimiter)

// Compression
app.use(compression({ level: 6 }))  // level 1-9, 6 is optimal balance

// CORS
app.use(cors({
  origin: process.env.CORS_ORIGIN?.split(',') ?? '*',
  methods: ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
  allowedHeaders: ['Content-Type', 'Authorization'],
  credentials: true,
  maxAge: 86400,  // 24h preflight cache
}))
```

```ts
// Nest.js rate limiting with @nestjs/throttler
// app.module.ts
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler'

@Module({
  imports: [
    ThrottlerModule.forRoot([{
      ttl: 60_000,
      limit: 10,
    }]),
  ],
  providers: [{ provide: APP_GUARD, useClass: ThrottlerGuard }],
})
export class AppModule {}
```

---

### Error Handling (God-Tier)

#### Custom Error Classes

```ts
// src/lib/errors.ts
export class AppError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly statusCode: number = 500,
    public readonly details?: unknown,
  ) {
    super(message)
    this.name = 'AppError'
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string, id?: string) {
    super(
      'NOT_FOUND',
      id ? `${resource} with id '${id}' not found` : `${resource} not found`,
      404,
    )
  }
}

export class ValidationError extends AppError {
  constructor(message: string, details?: unknown) {
    super('VALIDATION_ERROR', message, 400, details)
  }
}

export class AuthError extends AppError {
  constructor(message = 'Unauthorized') {
    super('UNAUTHORIZED', message, 401)
  }
}

export class ForbiddenError extends AppError {
  constructor(message = 'Forbidden') {
    super('FORBIDDEN', message, 403)
  }
}

export class ConflictError extends AppError {
  constructor(message: string) {
    super('CONFLICT', message, 409)
  }
}

export class RateLimitError extends AppError {
  constructor() {
    super('RATE_LIMIT', 'Too many requests', 429)
  }
}
```

#### Async Error Wrapper

```ts
// Express requires explicit error catching in async handlers

// Option 1: Wrap each handler
// src/lib/async-wrap.ts
import type { Request, Response, NextFunction, RequestHandler } from 'express'

export function asyncWrap(fn: (req: Request, res: Response, next: NextFunction) => Promise<void>): RequestHandler {
  return (req, res, next) => {
    fn(req, res, next).catch(next)
  }
}

// Usage:
router.get('/users', asyncWrap(async (req, res) => {
  const users = await db.user.findMany()
  res.json({ success: true, data: users })
}))

// Option 2: Use express-async-errors package (monkey-patches Express)
import 'express-async-errors'
// Now ALL async handlers automatically forward errors to error middleware

// Option 3: Install and use
// npm install express-async-errors
```

#### Structured Error Response Format

```ts
// src/middleware/error-handler.ts
import type { Request, Response, NextFunction } from 'express'
import { AppError } from '../lib/errors'
import { logger } from '../lib/logger'

export function errorHandler(err: Error, req: Request, res: Response, _next: NextFunction) {
  const requestId = req.requestId ?? 'unknown'

  if (err instanceof AppError) {
    logger.warn({
      code: err.code,
      message: err.message,
      statusCode: err.statusCode,
      requestId,
      path: req.path,
    }, 'Application error')

    return res.status(err.statusCode).json({
      success: false,
      error: {
        code: err.code,
        message: err.message,
        details: err.details ?? undefined,
        timestamp: new Date().toISOString(),
        requestId,
      },
    })
  }

  // Unknown error — log full stack, return generic
  logger.error({
    err: err.stack,
    requestId,
    path: req.path,
  }, 'Unhandled error')

  return res.status(500).json({
    success: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: process.env.NODE_ENV === 'production'
        ? 'An unexpected error occurred'
        : err.message,
      timestamp: new Date().toISOString(),
      requestId,
    },
  })
}
```

#### Zod Validation Middleware

```ts
// src/middleware/validate.ts
import type { Request, Response, NextFunction } from 'express'
import { z } from 'zod'
import { ValidationError } from '../lib/errors'

interface ValidationSchemas {
  body?: z.ZodSchema
  query?: z.ZodSchema
  params?: z.ZodSchema
}

export function validate(schemas: ValidationSchemas) {
  return (req: Request, _res: Response, next: NextFunction) => {
    try {
      if (schemas.body) req.body = schemas.body.parse(req.body)
      if (schemas.query) req.query = schemas.query.parse(req.query)
      if (schemas.params) req.params = schemas.params.parse(req.params)
      next()
    } catch (err) {
      if (err instanceof z.ZodError) {
        next(new ValidationError('Validation failed', err.errors.map(e => ({
          field: e.path.join('.'),
          message: e.message,
        }))))
      } else {
        next(err)
      }
    }
  }
}

// Usage:
router.post('/users', validate({
  body: z.object({
    name: z.string().min(1).max(100),
    email: z.string().email(),
    age: z.number().int().positive().optional(),
  }),
}), asyncWrap(async (req, res) => {
  const user = await createUser(req.body)
  res.status(201).json({ success: true, data: user })
}))
```

#### Error Monitoring Integration

```ts
// src/lib/sentry.ts
import * as Sentry from '@sentry/node'
import { nodeProfilingIntegration } from '@sentry/profiling-node'

export function initSentry() {
  if (!process.env.SENTRY_DSN) return

  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    environment: process.env.NODE_ENV,
    integrations: [nodeProfilingIntegration()],
    tracesSampleRate: parseFloat(process.env.SENTRY_SAMPLE_RATE ?? '0.1'),
    profilesSampleRate: 0.1,
  })
}

// Express integration
import * as Sentry from '@sentry/node'
app.use(Sentry.Handlers.requestHandler())
app.use(Sentry.Handlers.tracingHandler())
// ... routes ...
app.use(Sentry.Handlers.errorHandler())  // Must be AFTER all routes, before custom error handler
```

---

### Request/Response Patterns

#### Standardized Response Format

```ts
// src/lib/response.ts
export interface SuccessResponse<T> {
  success: true
  data: T
  meta?: {
    page: number
    perPage: number
    total: number
    totalPages: number
  }
  timestamp: string
}

export interface ErrorResponse {
  success: false
  error: {
    code: string
    message: string
    details?: unknown
    timestamp: string
    requestId: string
  }
}

export function success<T>(data: T, meta?: SuccessResponse<T>['meta']): SuccessResponse<T> {
  return { success: true, data, meta, timestamp: new Date().toISOString() }
}

export function paginated<T>(data: T[], total: number, page: number, perPage: number): SuccessResponse<T[]> {
  return {
    success: true,
    data,
    meta: {
      page,
      perPage,
      total,
      totalPages: Math.ceil(total / perPage),
    },
    timestamp: new Date().toISOString(),
  }
}
```

#### Request Validation

```ts
// Joi validation (alternative to Zod)
import Joi from 'joi'

const createUserSchema = Joi.object({
  name: Joi.string().min(1).max(100).required(),
  email: Joi.string().email().required(),
  age: Joi.number().integer().min(18).max(120),
})

// Zod (recommended — TypeScript first)
import { z } from 'zod'

export const CreateUserSchema = z.object({
  name: z.string().min(1, 'Name is required').max(100),
  email: z.string().email('Invalid email format'),
  age: z.number().int().positive().optional(),
})

export type CreateUserDto = z.infer<typeof CreateUserSchema>

// Nest.js class-validator
// src/users/dto/create-user.dto.ts
import { IsString, IsEmail, IsInt, Min, Max, IsOptional } from 'class-validator'

export class CreateUserDto {
  @IsString()
  @Min(1)
  name!: string

  @IsEmail()
  email!: string

  @IsOptional()
  @IsInt()
  @Min(18)
  @Max(120)
  age?: number
}
```

#### File Upload

```ts
// Express with multer
import multer from 'multer'
import path from 'node:path'
import { randomUUID } from 'node:crypto'

const storage = multer.diskStorage({
  destination: (_req, _file, cb) => cb(null, 'uploads/'),
  filename: (_req, file, cb) => {
    const ext = path.extname(file.originalname)
    cb(null, `${randomUUID()}${ext}`)
  },
})

const upload = multer({
  storage,
  limits: { fileSize: 5 * 1024 * 1024 },  // 5MB
  fileFilter: (_req, file, cb) => {
    const allowed = ['.jpg', '.jpeg', '.png', '.pdf']
    if (!allowed.includes(path.extname(file.originalname).toLowerCase())) {
      return cb(new Error('Invalid file type'))
    }
    cb(null, true)
  },
})

router.post('/upload', upload.single('file'), asyncWrap(async (req, res) => {
  if (!req.file) throw new ValidationError('No file uploaded')
  res.status(201).json({ success: true, data: { filename: req.file.filename, size: req.file.size } })
}))
```

#### Stream Handling

```ts
import { createReadStream } from 'node:fs'
import { stat } from 'node:fs/promises'
import type { Request, Response } from 'express'

async function streamFile(req: Request, res: Response) {
  const filePath = path.join(UPLOAD_DIR, req.params.filename)

  try {
    await stat(filePath)
  } catch {
    throw new NotFoundError('File', req.params.filename)
  }

  const stream = createReadStream(filePath)

  stream.on('error', (err) => {
    if (!res.headersSent) {
      res.status(500).json({ success: false, error: { code: 'STREAM_ERROR', message: 'File stream failed' } })
    }
  })

  res.setHeader('Content-Type', 'application/octet-stream')
  stream.pipe(res)
}
```

---

### Authentication & Authorization

#### JWT Authentication

```ts
// src/lib/jwt.ts
import jwt from 'jsonwebtoken'
import { randomBytes } from 'node:crypto'

const ACCESS_SECRET = process.env.JWT_ACCESS_SECRET! //  must be set
const REFRESH_SECRET = process.env.JWT_REFRESH_SECRET! //  must be set
const ACCESS_EXPIRY = '15m'
const REFRESH_EXPIRY = '7d'

export interface TokenPayload {
  userId: string
  role: string
}

export function signAccessToken(payload: TokenPayload): string {
  return jwt.sign(payload, ACCESS_SECRET, { expiresIn: ACCESS_EXPIRY })
}

export function signRefreshToken(payload: TokenPayload): string {
  return jwt.sign(payload, REFRESH_SECRET, { expiresIn: REFRESH_EXPIRY })
}

export function verifyAccessToken(token: string): TokenPayload {
  return jwt.verify(token, ACCESS_SECRET) as TokenPayload
}

export function verifyRefreshToken(token: string): TokenPayload {
  return jwt.verify(token, REFRESH_SECRET) as TokenPayload
}

// Token blacklist (use Redis in production)
const blacklist = new Set<string>()

export function blacklistToken(token: string) {
  blacklist.add(token)
  // Auto-remove after expiry
  setTimeout(() => blacklist.delete(token), 15 * 60 * 1000)
}

export function isBlacklisted(token: string): boolean {
  return blacklist.has(token)
}
```

#### Auth Middleware

```ts
// src/middleware/auth.ts
import type { Request, Response, NextFunction } from 'express'
import { verifyAccessToken, isBlacklisted } from '../lib/jwt'
import { AuthError } from '../lib/errors'

declare global {
  namespace Express {
    interface Request {
      user?: { userId: string; role: string }
    }
  }
}

export function authenticate(req: Request, _res: Response, next: NextFunction) {
  const header = req.headers.authorization
  if (!header?.startsWith('Bearer ')) {
    throw new AuthError('Missing or invalid authorization header')
  }

  const token = header.slice(7)
  if (isBlacklisted(token)) {
    throw new AuthError('Token has been revoked')
  }

  try {
    req.user = verifyAccessToken(token)
    next()
  } catch {
    throw new AuthError('Invalid or expired token')
  }
}

// Role-based authorization
export function authorize(...roles: string[]) {
  return (req: Request, _res: Response, next: NextFunction) => {
    if (!req.user) throw new AuthError()
    if (!roles.includes(req.user.role)) {
      throw new ForbiddenError('Insufficient permissions')
    }
    next()
  }
}

// Usage:
router.get('/admin', authenticate, authorize('admin', 'superadmin'), adminHandler)
```

#### Refresh Token Rotations

```ts
// src/routes/auth.ts
router.post('/refresh', asyncWrap(async (req, res) => {
  const { refreshToken } = req.body
  if (!refreshToken) throw new ValidationError('Refresh token required')

  try {
    const payload = verifyRefreshToken(refreshToken)

    // Issue new token pair (rotation)
    const newAccess = signAccessToken({ userId: payload.userId, role: payload.role })
    const newRefresh = signRefreshToken({ userId: payload.userId, role: payload.role })

    // Blacklist old refresh token
    blacklistToken(refreshToken)

    res.json({
      success: true,
      data: { accessToken: newAccess, refreshToken: newRefresh },
    })
  } catch {
    throw new AuthError('Invalid or expired refresh token')
  }
}))

router.post('/logout', authenticate, asyncWrap(async (req, res) => {
  const header = req.headers.authorization!
  const token = header.slice(7)
  blacklistToken(token)
  res.json({ success: true, data: { message: 'Logged out successfully' } })
}))
```

#### OAuth2 with Passport.js

```ts
// src/lib/passport.ts
import passport from 'passport'
import { Strategy as GoogleStrategy } from 'passport-google-oauth20'
import { Strategy as GitHubStrategy } from 'passport-github2'

passport.use(new GoogleStrategy({
  clientID: process.env.GOOGLE_CLIENT_ID!,
  clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
  callbackURL: '/api/v1/auth/google/callback',
}, async (_accessToken, _refreshToken, profile, done) => {
  const user = await findOrCreateUser({
    email: profile.emails?.[0]?.value ?? '',
    name: profile.displayName,
    provider: 'google',
    providerId: profile.id,
  })
  done(null, user)
}))

// Express routes
router.get('/google', passport.authenticate('google', { scope: ['profile', 'email'] }))
router.get('/google/callback', passport.authenticate('google', { session: false }), (req, res) => {
  const token = signAccessToken({ userId: req.user!.id, role: req.user!.role })
  res.redirect(`${process.env.CLIENT_URL}/auth/callback?token=${token}`)
})
```

#### API Key Authentication

```ts
// src/middleware/api-key.ts
import type { Request, Response, NextFunction } from 'express'
import { AuthError } from '../lib/errors'

const API_KEYS = new Map<string, { service: string; permissions: string[] }>()
// Populate from database at startup

export function authenticateApiKey(req: Request, _res: Response, next: NextFunction) {
  const key = req.headers['x-api-key'] as string
  if (!key) throw new AuthError('API key required')

  const service = API_KEYS.get(key)
  if (!service) throw new AuthError('Invalid API key')

  req.service = service  // attach service info
  next()
}

// Usage in service-to-service communication only
router.use('/api/v1/internal', authenticateApiKey)
```

---

### Database Integration

#### ORM vs Query Builder vs Raw SQL Decision Tree

```
How to access the database?
              │
              ▼
  ┌───────────┴───────────┐
  │                       │
  Does the team prefer    Needs maximum
  TypeScript-first        performance and
  schema definition?      complex queries?
  │                       │
  │                       │
 YES                     YES
  │                       │
  ▼                       ▼
Prisma ORM             Raw SQL
(Prisma schema →      (pg driver +
  full type safety,     SQL templates,
  migrations,           full control)
  relations)
              │
              │
              │
              ▼
       Hybrid approach
       ─────────────────
       Prisma for CRUD operations (80%)
       Raw SQL for complex reporting / aggregations (20%)
       Query timing: use Prisma's middleware to log slow queries
```

#### Prisma ORM

```ts
// schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(uuid())
  email     String   @unique
  name      String
  role      String   @default("user")
  posts     Post[]
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}

model Post {
  id        String   @id @default(uuid())
  title     String
  content   String?
  published Boolean  @default(false)
  authorId  String
  author    User     @relation(fields: [authorId], references: [id])
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
}
```

```ts
// src/lib/prisma.ts
import { PrismaClient } from '@prisma/client'
import { logger } from './logger'

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient | undefined }

export const prisma = globalForPrisma.prisma ?? new PrismaClient({
  log: ['query', 'warn', 'error'],
})

// Prevent multiple instances in development (hot reload)
if (process.env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma

// Middleware: measure query performance
prisma.$use(async (params, next) => {
  const start = performance.now()
  const result = await next(params)
  const duration = performance.now() - start

  if (duration > 100) {
    logger.warn({ model: params.model, action: params.action, duration: `${duration.toFixed(2)}ms` }, 'Slow query')
  }

  return result
})
```

```ts
// Prisma: pagination, filtering, transactions

// Cursor-based pagination
async function getUsers(cursor?: string, limit = 20) {
  return prisma.user.findMany({
    take: limit,
    skip: cursor ? 1 : 0,  // skip the cursor itself
    cursor: cursor ? { id: cursor } : undefined,
    orderBy: { createdAt: 'desc' },
    select: { id: true, name: true, email: true, createdAt: true },
  })
}

// Offset-based pagination
async function getUsersPaginated(page = 1, perPage = 20) {
  const [data, total] = await Promise.all([
    prisma.user.findMany({
      skip: (page - 1) * perPage,
      take: perPage,
      orderBy: { createdAt: 'desc' },
    }),
    prisma.user.count(),
  ])
  return { data, total, page, perPage, totalPages: Math.ceil(total / perPage) }
}

// Nested transactions
async function transferFunds(fromId: string, toId: string, amount: number) {
  return prisma.$transaction(async (tx) => {
    const from = await tx.account.findUniqueOrThrow({ where: { id: fromId } })
    const to = await tx.account.findUniqueOrThrow({ where: { id: toId } })
    if (from.balance < amount) throw new ValidationError('Insufficient funds')

    await tx.account.update({ where: { id: fromId }, data: { balance: { decrement: amount } } })
    await tx.account.update({ where: { id: toId }, data: { balance: { increment: amount } } })

    await tx.transaction.create({
      data: { fromId, toId, amount, type: 'TRANSFER' },
    })
  })  // Auto-rollback on ANY error
}

// Batched operations
async function bulkCreateUsers(users: Array<{ name: string; email: string }>) {
  return prisma.$transaction(
    users.map(u => prisma.user.create({ data: u })),
    { maxWait: 5000, timeout: 10000 },
  )
}
```

#### Drizzle ORM (Type-Safe SQL)

```ts
// src/db/schema.ts
import { pgTable, uuid, text, timestamp, boolean } from 'drizzle-orm/pg-core'

export const users = pgTable('users', {
  id: uuid('id').defaultRandom().primaryKey(),
  email: text('email').notNull().unique(),
  name: text('name').notNull(),
  role: text('role').default('user'),
  createdAt: timestamp('created_at').defaultNow().notNull(),
  updatedAt: timestamp('updated_at').defaultNow().notNull(),
})

// src/db/index.ts
import { drizzle } from 'drizzle-orm/node-postgres'
import { Pool } from 'pg'
import * as schema from './schema'

const pool = new Pool({ connectionString: process.env.DATABASE_URL })
export const db = drizzle(pool, { schema })
```

```ts
// Drizzle queries (SQL-like, type-safe)
import { db } from '../db'
import { users } from '../db/schema'
import { eq, ilike, desc, and, sql, count } from 'drizzle-orm'

// SELECT with conditions
const result = await db
  .select({
    id: users.id,
    name: users.name,
    email: users.email,
  })
  .from(users)
  .where(and(eq(users.role, 'admin'), ilike(users.name, '%john%')))
  .orderBy(desc(users.createdAt))
  .limit(20)
  .offset(0)

// INSERT
const [newUser] = await db
  .insert(users)
  .values({ name: 'Alice', email: 'alice@test.com' })
  .returning()

// UPDATE
await db
  .update(users)
  .set({ name: 'Bob' })
  .where(eq(users.id, 'some-id'))

// DELETE
await db.delete(users).where(eq(users.id, 'some-id'))

// Raw SQL with Drizzle
const result = await db.execute(
  sql`SELECT * FROM users WHERE email LIKE ${'%@example.com'}`
)
```

#### Raw SQL with pg (node-postgres)

```ts
// src/db/pool.ts
import { Pool } from 'pg'

export const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,                 // maximum pool size
  idleTimeoutMillis: 30_000,
  connectionTimeoutMillis: 5_000,
})

pool.on('error', (err) => {
  logger.error({ err }, 'Unexpected database pool error')
})

// Health check
export async function checkDbHealth(): Promise<boolean> {
  try {
    await pool.query('SELECT 1')
    return true
  } catch {
    return false
  }
}
```

```ts
// src/db/queries.ts
import { pool } from './pool'

// Parameterized queries (SQL injection safe)
export async function findUserByEmail(email: string) {
  const { rows } = await pool.query(
    'SELECT id, name, email, role FROM users WHERE email = $1',
    [email],
  )
  return rows[0] ?? null
}

// Paginated query with filters
export async function getUsers(options: {
  page: number; perPage: number; search?: string; role?: string
}) {
  const { page, perPage, search, role } = options
  const conditions: string[] = []
  const params: unknown[] = []
  let paramIndex = 1

  if (search) {
    conditions.push(`(name ILIKE $${paramIndex} OR email ILIKE $${paramIndex})`)
    params.push(`%${search}%`)
    paramIndex++
  }
  if (role) {
    conditions.push(`role = $${paramIndex}`)
    params.push(role)
    paramIndex++
  }

  const whereClause = conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : ''
  const countResult = await pool.query(`SELECT COUNT(*) FROM users ${whereClause}`, params)
  const total = parseInt(countResult.rows[0].count, 10)

  params.push(perPage)
  params.push((page - 1) * perPage)
  const dataResult = await pool.query(
    `SELECT id, name, email, role, created_at
     FROM users ${whereClause}
     ORDER BY created_at DESC
     LIMIT $${paramIndex} OFFSET $${paramIndex + 1}`,
    params,
  )

  return { data: dataResult.rows, total, page, perPage }
}

// Transaction with savepoint
export async function createUserWithProfile(data: { name: string; email: string; bio?: string }) {
  const client = await pool.connect()
  try {
    await client.query('BEGIN')
    const { rows: [user] } = await client.query(
      'INSERT INTO users (name, email) VALUES ($1, $2) RETURNING *',
      [data.name, data.email],
    )
    if (data.bio) {
      await client.query(
        'INSERT INTO profiles (user_id, bio) VALUES ($1, $2)',
        [user.id, data.bio],
      )
    }
    await client.query('COMMIT')
    return user
  } catch (err) {
    await client.query('ROLLBACK')
    throw err
  } finally {
    client.release()
  }
}
```

#### Connection Pooling Best Practices

```
┌────────────────────────────────────────────────────┐
│              CONNECTION POOLING                     │
│                                                      │
│  Pool size formula:                                  │
│  pool_max = (max_connections - superuser_reserved)   │
│             / number_of_application_instances        │
│                                                      │
│  Example: PostgreSQL max_connections = 100           │
│           3 app instances                            │
│           superuser_reserved = 3                     │
│           pool_max = (100 - 3) / 3 ≈ 32 per instance │
│                                                      │
│  Rules:                                              │
│  • pool_max × instances < db_max_connections         │
│  • Monitor `idle_in_transaction` timeout             │
│  • Set statement_timeout = 30s at pool level         │
│  • Use PgBouncer in transaction mode for serverless  │
└────────────────────────────────────────────────────┘
```

#### Migration Strategy

```ts
// Prisma migrations (recommended)
// npx prisma migrate dev          -- create & apply migration in dev
// npx prisma migrate deploy       -- apply in production (safe)
// npx prisma migrate status       -- check pending migrations
// npx prisma migrate resolve      -- fix migration history

// Zero-downtime migration pattern:
// 1. Expand: add new columns/tables (nullable or with defaults)
// 2. Migrate: update application to write to both old and new
// 3. Double-read: verify data consistency
// 4. Migrate data: backfill existing records
// 5. Contract: remove old columns

// Knex.js migrations
// npx knex migrate:make add_user_role
// npx knex migrate:latest
// npx knex migrate:rollback

// src/db/migrations/20260517_add_user_role.ts
import type { Knex } from 'knex'

export async function up(knex: Knex): Promise<void> {
  await knex.schema.alterTable('users', (table) => {
    table.string('role', 20).defaultTo('user')
    table.index('role')
  })
}

export async function down(knex: Knex): Promise<void> {
  await knex.schema.alterTable('users', (table) => {
    table.dropIndex('role')
    table.dropColumn('role')
  })
}
```

#### Transaction Saga Pattern (Distributed)

```ts
// Orchestrator-based saga for distributed transactions
// Example: Order → Payment → Inventory → Notification

interface SagaStep<T> {
  name: string
  execute: (context: T) => Promise<void>
  compensate: (context: T) => Promise<void>
}

async function executeSaga<T>(steps: SagaStep<T>[], context: T): Promise<void> {
  const executedSteps: SagaStep<T>[] = []

  for (const step of steps) {
    try {
      await step.execute(context)
      executedSteps.push(step)
    } catch (err) {
      logger.error({ step: step.name, err }, 'Saga step failed, initiating rollback')

      // Compensate in reverse order
      for (const executed of executedSteps.reverse()) {
        try {
          await executed.compensate(context)
          logger.info({ step: executed.name }, 'Compensation succeeded')
        } catch (compErr) {
          logger.error({ step: executed.name, err: compErr }, 'Compensation failed — manual intervention required')
        }
      }

      throw err
    }
  }
}
```

---

### API Design

#### RESTful Conventions

```
GET    /api/v1/users              → List users (index)
POST   /api/v1/users              → Create user (create)
GET    /api/v1/users/:id          → Get user (show)
PUT    /api/v1/users/:id          → Replace user (update)
PATCH  /api/v1/users/:id          → Partial update (modify)
DELETE /api/v1/users/:id          → Delete user (destroy)

GET    /api/v1/users/:id/posts    → List user's posts (nested resource)
POST   /api/v1/users/:id/posts    → Create post for user

Naming:
  • Plural nouns: /users NOT /user
  • Nesting max 2 levels deep
  • Kebab-case: /order-history NOT /order_history
  • Query params for filtering, NOT path params
```

#### Pagination Decision Tree

```
Which pagination strategy?
              │
              ▼
    ┌─────────┴─────────┐
    │                    │
  Is the data           Does the list
  append-only?          reorder frequently?
  (e.g., logs,          (e.g., search
   notifications)        results, ranked)
    │                    │
   YES                   YES
    │                    │
    ▼                    ▼
Cursor-based          Cursor-based
(WHERE id > last)    (WHERE score < last_score)
  Cursor: base64         Cursor: base64
  encoded ID             encoded value
  Stable position        May skip if scores tie
                        (add id to cursor)
    │                    │
    ▼                    ▼
Fast, consistent     Slightly complex
                    │                    │
                    NO                    NO
                    │                    │
                    ▼                    ▼
              Offset-based           Offset-based
              (OFFSET x LIMIT y)     (ORDER BY + OFFSET)
              Simple, but:           Works, but:
              - page drift (inserts  - page drift
                shift results)       - slow on large
              - slow on large OFFSET  OFFSET (>100k)
```

```
Cursor Pagination Diagram:

Request:  GET /api/users?cursor=eyJpZCI6IjEyMyJ9&limit=20
                                                │
                                                ▼
┌─────────────────────────────────────────────────────────┐
│ Server decodes cursor → { id: "123" }                    │
│ Query: SELECT * FROM users                               │
│        WHERE id > '123'                                  │
│        ORDER BY id ASC                                   │
│        LIMIT 21         ← fetch one extra to check "hasMore" │
└─────────────────────────┬───────────────────────────────┘
                          ▼
Response: {
  data: [ ...20 items ],
  meta: {
    cursor: base64({ id: "last_item_id" }),
    hasMore: true     // because we fetched 21 but returned 20
  }
}
```

#### Filtering, Sorting, Field Selection

```ts
// Standardized query parameter conventions
// GET /api/v1/users?search=john&role=admin&sort=-createdAt&fields=id,name,email&page=1&perPage=20

interface QueryOptions {
  search?: string
  filters: Record<string, string>
  sort: { field: string; order: 'asc' | 'desc' }[]
  fields: string[]
  page: number
  perPage: number
}

function parseQueryOptions(query: Record<string, string | undefined>): QueryOptions {
  const filters: Record<string, string> = {}

  // Known filterable fields (whitelist approach — security)
  const filterableFields = ['role', 'status', 'isActive']
  for (const field of filterableFields) {
    if (query[field]) filters[field] = query[field]
  }

  // Sorting: -createdAt = descending, createdAt = ascending
  const sort: QueryOptions['sort'] = []
  if (query.sort) {
    query.sort.split(',').forEach(s => {
      const order = s.startsWith('-') ? 'desc' : 'asc'
      sort.push({ field: s.replace(/^[-+]/, ''), order })
    })
  }

  return {
    search: query.search,
    filters,
    sort,
    fields: query.fields?.split(',').filter(Boolean) ?? [],
    page: Math.max(1, parseInt(query.page ?? '1', 10)),
    perPage: Math.min(100, Math.max(1, parseInt(query.perPage ?? '20', 10))),
  }
}
```

#### OpenAPI/Swagger Documentation

```ts
// Express with swagger-jsdoc + swagger-ui-express
import swaggerJsdoc from 'swagger-jsdoc'
import swaggerUi from 'swagger-ui-express'

const swaggerSpec = swaggerJsdoc({
  definition: {
    openapi: '3.0.0',
    info: { title: 'My API', version: '1.0.0' },
    servers: [{ url: '/api/v1' }],
    components: {
      securitySchemes: {
        bearerAuth: { type: 'http', scheme: 'bearer', bearerFormat: 'JWT' },
      },
    },
  },
  apis: ['./src/routes/*.ts'],
})

app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec, {
  customCss: '.swagger-ui .topbar { display: none }',
  swaggerOptions: { persistAuthorization: true },
}))
```

```ts
// JSDoc annotations for route files
/**
 * @openapi
 * /users:
 *   get:
 *     tags: [Users]
 *     summary: List all users
 *     security:
 *       - bearerAuth: []
 *     parameters:
 *       - in: query
 *         name: page
 *         schema: { type: integer, default: 1 }
 *       - in: query
 *         name: perPage
 *         schema: { type: integer, default: 20 }
 *     responses:
 *       200:
 *         description: Paginated list of users
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success: { type: boolean }
 *                 data: { type: array, items: { $ref: '#/components/schemas/User' } }
 *                 meta:
 *                   type: object
 *                   properties:
 *                     page: { type: integer }
 *                     total: { type: integer }
 */
router.get('/', authenticate, asyncWrap(getUsers))
```

#### Versioning Strategies

```
URL-based (recommended for public APIs):
  GET /api/v1/users
  GET /api/v2/users

Header-based (clean URLs, harder to discover):
  Accept: application/vnd.api.v1+json
  Accept: application/vnd.api.v2+json

Subdomain-based (for completely separate services):
  v1.api.example.com/users
  v2.api.example.com/users

Strategy: use URL-based versioning for public APIs,
keep previous version alive for 6 months with deprecation notice
```

---

### Async Patterns

#### Async/Await Best Practices

```ts
// ✅ GOOD: proper error handling with try/catch
async function getUser(id: string) {
  try {
    const user = await db.user.findUnique({ where: { id } })
    if (!user) throw new NotFoundError('User', id)
    return user
  } catch (err) {
    // Re-throw AppError, wrap unknown errors
    if (err instanceof AppError) throw err
    throw new AppError('DATABASE_ERROR', 'Failed to fetch user', 500)
  }
}

// ✅ GOOD: parallel execution for independent tasks
async function getUserWithPosts(id: string) {
  const [user, posts] = await Promise.all([
    db.user.findUnique({ where: { id } }),
    db.post.findMany({ where: { authorId: id } }),
  ])
  return { user, posts }
}

// ✅ GOOD: Promise.allSettled for partial failures
async function sendBulkNotifications(userIds: string[], message: string) {
  const results = await Promise.allSettled(
    userIds.map(id => sendNotification(id, message))
  )

  const failed = results.filter((r): r is PromiseRejectedResult => r.status === 'rejected')
  if (failed.length > 0) {
    logger.warn({ count: failed.length, total: userIds.length }, 'Some notifications failed')
  }

  return { sent: userIds.length - failed.length, failed: failed.length }
}

// ❌ BAD: unawaited promise (fire-and-forget without error handling)
function badProcess(userId: string) {
  processUser(userId)  // unhandled rejection if it fails!
}

// ✅ GOOD: proper fire-and-forget with error handler
function goodProcess(userId: string) {
  processUser(userId).catch((err) => {
    logger.error({ userId, err }, 'Background processing failed')
  })
}
```

#### EventEmitter Patterns

```ts
// src/lib/events.ts
import EventEmitter from 'node:events'

interface AppEvents {
  'user:created': { userId: string; email: string }
  'user:deleted': { userId: string }
  'order:placed': { orderId: string; total: number }
}

class AppEventEmitter extends EventEmitter {
  emit<K extends keyof AppEvents>(event: K, data: AppEvents[K]): boolean {
    return super.emit(event as string, data)
  }

  on<K extends keyof AppEvents>(event: K, listener: (data: AppEvents[K]) => void): this {
    return super.on(event as string, listener)
  }
}

export const appEvents = new AppEventEmitter()

// Subscribe (in module initialization)
appEvents.on('user:created', async ({ userId, email }) => {
  await sendWelcomeEmail(email)
  logger.info({ userId }, 'Welcome email sent')
})

// Emit (in service)
appEvents.emit('user:created', { userId: user.id, email: user.email })
```

#### Worker Threads for CPU-Intensive Tasks

```ts
// src/workers/image-processor.ts
import { parentPort, workerData } from 'node:worker_threads'
import sharp from 'sharp'  // CPU-intensive image processing

interface ProcessJob {
  inputPath: string
  outputPath: string
  width: number
  height: number
}

async function processImage(job: ProcessJob) {
  await sharp(job.inputPath)
    .resize(job.width, job.height)
    .jpeg({ quality: 80 })
    .toFile(job.outputPath)

  return { path: job.outputPath, size: job.width }
}

parentPort!.on('message', async (job: ProcessJob) => {
  try {
    const result = await processImage(job)
    parentPort!.postMessage({ success: true, data: result })
  } catch (err) {
    parentPort!.postMessage({ success: false, error: (err as Error).message })
  }
})
```

```ts
// Main thread usage
import { Worker } from 'node:worker_threads'
import path from 'node:path'

function processImageInWorker(job: { inputPath: string; outputPath: string; width: number; height: number }) {
  return new Promise((resolve, reject) => {
    const worker = new Worker(path.join(__dirname, 'workers/image-processor.js'))

    worker.postMessage(job)

    worker.on('message', (result) => {
      worker.terminate()
      if (result.success) resolve(result.data)
      else reject(new Error(result.error))
    })

    worker.on('error', (err) => {
      worker.terminate()
      reject(err)
    })
  })
}
```

#### BullMQ for Background Jobs

```ts
// src/lib/queue.ts
import { Queue, Worker, QueueScheduler } from 'bullmq'
import Redis from 'ioredis'

const connection = new Redis(process.env.REDIS_URL!, {
  maxRetriesPerRequest: null,
  enableReadyCheck: false,
})

// Define queues
export const emailQueue = new Queue('email', { connection })
export const reportQueue = new Queue('report', { connection })
export const webhookQueue = new Queue('webhook', { connection })

// Add jobs
await emailQueue.add('welcome-email', {
  to: user.email,
  template: 'welcome',
  data: { name: user.name },
}, {
  attempts: 3,
  backoff: { type: 'exponential', delay: 2000 },
  removeOnComplete: { age: 3600 },
})

// Process jobs (in a separate worker process)
// src/workers/email-worker.ts
import { Worker } from 'bullmq'

const worker = new Worker('email', async (job) => {
  const { to, template, data } = job.data
  await sendEmail({ to, template, data })
}, { connection, concurrency: 10 })

worker.on('completed', (job) => {
  logger.info({ jobId: job.id }, 'Email sent')
})

worker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err }, 'Email failed')
})
```

#### WebSocket with Socket.io

```ts
// src/lib/socket.ts
import { Server as HttpServer } from 'node:http'
import { Server } from 'socket.io'
import { verifyAccessToken } from './jwt'
import type { AuthError } from './errors'

let io: Server

export function initSocket(httpServer: HttpServer) {
  io = new Server(httpServer, {
    cors: {
      origin: process.env.CORS_ORIGIN,
      credentials: true,
    },
    pingInterval: 25_000,  // 25s heartbeat
    pingTimeout: 20_000,    // 20s wait for pong
  })

  // Auth middleware
  io.use((socket, next) => {
    const token = socket.handshake.auth.token ?? socket.handshake.headers.authorization
    if (!token) return next(new Error('Authentication required'))

    try {
      const user = verifyAccessToken(token.replace('Bearer ', ''))
      socket.data.user = user
      next()
    } catch {
      next(new Error('Invalid token'))
    }
  })

  io.on('connection', (socket) => {
    const { userId } = socket.data.user

    logger.info({ userId, socketId: socket.id }, 'Socket connected')

    // Join user-specific room for private messages
    socket.join(`user:${userId}`)

    socket.on('disconnect', (reason) => {
      logger.info({ userId, socketId: socket.id, reason }, 'Socket disconnected')
    })
  })

  return io
}

// Emit to specific user
export function sendToUser(userId: string, event: string, data: unknown) {
  io.to(`user:${userId}`).emit(event, data)
}

// Emit to all connected clients
export function broadcast(event: string, data: unknown) {
  io.emit(event, data)
}
```

---

### Testing (Comprehensive)

#### Vitest Configuration

```ts
// vitest.config.ts
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    globals: true,
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      include: ['src/**/*.ts'],
      exclude: ['src/test/**', 'src/**/*.d.ts'],
      thresholds: {
        statements: 80,
        branches: 75,
        functions: 80,
        lines: 80,
      },
    },
    testTimeout: 10_000,
    hookTimeout: 15_000,
  },
})
```

```ts
// src/test/setup.ts
import { beforeAll, afterAll, beforeEach, afterEach } from 'vitest'

// Set test environment
process.env.NODE_ENV = 'test'
process.env.DATABASE_URL = 'postgres://test:test@localhost:5432/test'
process.env.JWT_ACCESS_SECRET = 'test-access-secret'
process.env.JWT_REFRESH_SECRET = 'test-refresh-secret'
process.env.REDIS_URL = 'redis://localhost:6379'
```

#### Unit Tests (Isolated)

```ts
// src/users/users.service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { UsersService } from './users.service'

// Mock Prisma
const mockPrisma = {
  user: {
    findUnique: vi.fn(),
    findMany: vi.fn(),
    create: vi.fn(),
    count: vi.fn(),
  },
  $transaction: vi.fn(),
}

describe('UsersService', () => {
  let service: UsersService

  beforeEach(() => {
    vi.clearAllMocks()
    service = new UsersService(mockPrisma as any)
  })

  describe('findById', () => {
    it('returns user when found', async () => {
      const mockUser = { id: '1', name: 'Alice', email: 'alice@test.com' }
      mockPrisma.user.findUnique.mockResolvedValue(mockUser)

      const result = await service.findById('1')

      expect(result).toEqual(mockUser)
      expect(mockPrisma.user.findUnique).toHaveBeenCalledWith({
        where: { id: '1' },
      })
    })

    it('throws NotFoundError when user not found', async () => {
      mockPrisma.user.findUnique.mockResolvedValue(null)

      await expect(service.findById('999')).rejects.toThrow('User not found')
    })
  })

  describe('create', () => {
    it('creates and returns user', async () => {
      const dto = { name: 'Bob', email: 'bob@test.com' }
      const mockUser = { id: '2', ...dto }
      mockPrisma.user.create.mockResolvedValue(mockUser)

      const result = await service.create(dto)

      expect(result).toEqual(mockUser)
      expect(mockPrisma.user.create).toHaveBeenCalledWith({ data: dto })
    })
  })
})
```

#### Integration Tests with Supertest

```ts
// src/routes/users.test.ts
import { describe, it, expect, beforeAll, afterAll, vi } from 'vitest'
import supertest from 'supertest'
import { createApp } from '../app'

// Mock database at module level
vi.mock('../lib/prisma', () => ({
  prisma: {
    user: {
      findUnique: vi.fn(),
      findMany: vi.fn(),
      create: vi.fn(),
      count: vi.fn(),
    },
  },
}))

import { prisma } from '../lib/prisma'

let app: Express.Application

beforeAll(() => {
  app = createApp()
})

describe('GET /api/v1/users', () => {
  it('returns paginated users', async () => {
    const mockUsers = [
      { id: '1', name: 'Alice', email: 'alice@test.com', role: 'user', createdAt: new Date(), updatedAt: new Date() },
    ]
    vi.mocked(prisma.user.findMany).mockResolvedValue(mockUsers)
    vi.mocked(prisma.user.count).mockResolvedValue(1)

    const response = await supertest(app)
      .get('/api/v1/users')
      .expect(200)

    expect(response.body.success).toBe(true)
    expect(response.body.data).toHaveLength(1)
    expect(response.body.meta.total).toBe(1)
  })
})
```

```ts
// Testing authenticated endpoints
describe('POST /api/v1/users', () => {
  it('creates user when authorized', async () => {
    const newUser = { name: 'Charlie', email: 'charlie@test.com' }
    vi.mocked(prisma.user.create).mockResolvedValue({
      id: '3', ...newUser, role: 'user', createdAt: new Date(), updatedAt: new Date(),
    })

    const response = await supertest(app)
      .post('/api/v1/users')
      .set('Authorization', `Bearer ${generateTestToken()}`)
      .send(newUser)
      .expect(201)

    expect(response.body.success).toBe(true)
    expect(response.body.data.name).toBe('Charlie')
  })

  it('returns 401 without auth token', async () => {
    await supertest(app)
      .post('/api/v1/users')
      .send({ name: 'test' })
      .expect(401)
  })

  it('returns 400 for invalid payload', async () => {
    await supertest(app)
      .post('/api/v1/users')
      .set('Authorization', `Bearer ${generateTestToken()}`)
      .send({ name: '' })  // empty name
      .expect(400)
  })
})

// Helper to generate test tokens
import jwt from 'jsonwebtoken'

function generateTestToken(overrides = {}) {
  return jwt.sign(
    { userId: 'test-user', role: 'admin', ...overrides },
    process.env.JWT_ACCESS_SECRET!,
    { expiresIn: '1h' },
  )
}
```

#### Integration Tests with Testcontainers

```ts
// src/test/db-integration.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { PostgreSqlContainer } from '@testcontainers/postgresql'
import { Client } from 'pg'

let container: PostgreSqlContainer
let client: Client

beforeAll(async () => {
  container = await new PostgreSqlContainer('postgres:16')
    .withDatabase('testdb')
    .start()

  client = new Client({
    host: container.getHost(),
    port: container.getPort(),
    database: container.getDatabase(),
    user: container.getUsername(),
    password: container.getPassword(),
  })
  await client.connect()

  // Run migrations
  const migrationSql = await fs.readFile('./db/migrations/001_schema.sql', 'utf-8')
  await client.query(migrationSql)
}, 30_000)

afterAll(async () => {
  await client.end()
  await container.stop()
})

it('inserts and retrieves user', async () => {
  await client.query(
    'INSERT INTO users (id, name, email) VALUES ($1, $2, $3)',
    ['test-id', 'Test User', 'test@test.com'],
  )

  const { rows } = await client.query(
    'SELECT * FROM users WHERE id = $1',
    ['test-id'],
  )

  expect(rows[0].name).toBe('Test User')
})
```

#### E2E Tests

```ts
// e2e/api/users.spec.ts
import { test, expect } from '@playwright/test'

const BASE_URL = 'http://localhost:3000'

test.describe('Users API', () => {
  let authToken: string

  test.beforeAll(async ({ request }) => {
    const response = await request.post(`${BASE_URL}/api/v1/auth/login`, {
      data: { email: 'admin@test.com', password: 'test123' },
    })
    const body = await response.json()
    authToken = body.data.accessToken
  })

  test('complete user CRUD flow', async ({ request }) => {
    // Create
    const createRes = await request.post(`${BASE_URL}/api/v1/users`, {
      headers: { Authorization: `Bearer ${authToken}` },
      data: { name: 'E2E User', email: `e2e-${Date.now()}@test.com` },
    })
    expect(createRes.ok()).toBeTruthy()
    const { data: created } = await createRes.json()

    // Read
    const getRes = await request.get(`${BASE_URL}/api/v1/users/${created.id}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(getRes.ok()).toBeTruthy()

    // Delete
    const deleteRes = await request.delete(`${BASE_URL}/api/v1/users/${created.id}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(deleteRes.ok()).toBeTruthy()

    // Verify deleted
    const getDeleted = await request.get(`${BASE_URL}/api/v1/users/${created.id}`, {
      headers: { Authorization: `Bearer ${authToken}` },
    })
    expect(getDeleted.status()).toBe(404)
  })
})
```

#### Seed Factories with Faker

```ts
// src/test/factories.ts
import { faker } from '@faker-js/faker'

export function createUser(overrides: Partial<{
  name: string; email: string; role: string; isActive: boolean
}> = {}) {
  return {
    name: faker.person.fullName(),
    email: faker.internet.email().toLowerCase(),
    role: faker.helpers.arrayElement(['user', 'admin', 'moderator']),
    isActive: true,
    ...overrides,
  }
}

export function createPost(overrides: Partial<{
  title: string; content: string; published: boolean; authorId: string
}> = {}) {
  return {
    title: faker.lorem.sentence(),
    content: faker.lorem.paragraphs(3),
    published: faker.datatype.boolean(),
    authorId: 'default-author-id',
    ...overrides,
  }
}

export function createMany<T>(factory: (overrides?: Partial<T>) => T, count: number, overrides?: Partial<T>): T[] {
  return Array.from({ length: count }, () => factory(overrides))
}
```

---

### Security

#### OWASP Top 10 Mitigation

```
OWASP Top 10 (2021) — Node.js Mitigation
────────────────────────────────────────────────────────────────

A01: Broken Access Control
  → JWT + RBAC middleware on every protected route
  → Validate permissions in middleware, not in handler

A02: Cryptographic Failures
  → Never store passwords in plain text (bcrypt with cost 12)
  → HTTPS only (redirect HTTP → HTTPS)
  → No secrets in code, use environment variables

A03: Injection
  → Parameterized queries (NEVER string concatenation for SQL)
  → Input validation with Zod/Joi (whitelist approach)
  → Escape user input in HTML (if rendering)
  → Use ORM with parameterized queries

A04: Insecure Design
  → Rate limiting on auth endpoints (5 req/15min)
  → Account lockout after 5 failed attempts
  → Request size limits (10kb body limit)
  → Validate Content-Type headers

A05: Security Misconfiguration
  → helmet() with strict CSP
  → Disable x-powered-by header
  → No default credentials
  → CORS restricted to known origins
  → No stack traces in production errors

A06: Vulnerable Components
  → npm audit in CI pipeline
  → Dependabot / Renovate for auto-updates
  → Lockfile (package-lock.json) in git
  → Regular dependency audits (npm audit --production)

A07: Authentication Failures
  → Password complexity requirements (min 8 chars, mixed case, number)
  → bcrypt with cost factor 12
  → Refresh token rotation + blacklisting
  → Session timeout — 15min access token, 7d refresh token
  → No session fixation (issue new session on login)

A08: Data Integrity Failures
  → JWT signature verification (HS256 or RS256)
  → No unsigned JWTs
  → CSP for content integrity
  → Subresource Integrity (SRI) for CDN assets

A09: Logging & Monitoring
  → Structured JSON logging
  → Log all auth events (login, logout, failed attempts)
  → Centralized log aggregation (ELK / Grafana Loki)
  → Alert on unusual patterns (100+ failed logins in 5min)

A10: SSRF
  → Validate/whitelist URLs for outbound requests
  → Block private IP ranges (127.0.0.0/8, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
  → Use URL parser to validate, don't rely on regex
```

```ts
// URL validation for SSRF prevention
function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    const blockedIpRegex = /^(127\.|10\.|172\.(1[6-9]|2[0-9]|3[01])|192\.168\.)/
    const hostname = parsed.hostname

    // Block internal/private IPs
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return false
    }

    // Block by IP range
    if (blockedIpRegex.test(hostname)) return false

    // Only allow HTTPS for external calls
    return parsed.protocol === 'https:'
  } catch {
    return false
  }
}
```

#### SQL Injection Prevention

```ts
// ❌ VULNERABLE: string concatenation — NEVER use this
const query = `SELECT * FROM users WHERE email = '${userInput}'`

// ✅ SAFE: parameterized query with pg
const { rows } = await pool.query('SELECT * FROM users WHERE email = $1', [userInput])

// ✅ SAFE: Prisma (uses parameterized queries internally)
await prisma.user.findUnique({ where: { email: userInput } })

// ✅ SAFE: Drizzle (template SQL tags)
await db.select().from(users).where(eq(users.email, userInput))
```

#### CSRF Protection

```ts
// For session-based auth (not JWT — JWT doesn't need CSRF protection)
// CSRF protection with double-submit cookie pattern

// src/middleware/csrf.ts
import crypto from 'node:crypto'
import type { Request, Response, NextFunction } from 'express'

export function csrfProtection(req: Request, res: Response, next: NextFunction) {
  // Skip for GET, HEAD, OPTIONS (safe methods)
  if (['GET', 'HEAD', 'OPTIONS'].includes(req.method)) {
    return next()
  }

  const cookieToken = req.cookies?.['csrf-token']
  const headerToken = req.headers['x-csrf-token']
  const bodyToken = req.body?._csrf

  const sentToken = headerToken ?? bodyToken

  if (!cookieToken || !sentToken || cookieToken !== sentToken) {
    return res.status(403).json({
      success: false,
      error: { code: 'CSRF', message: 'Invalid CSRF token' },
    })
  }

  next()
}

// Generate CSRF token endpoint
router.get('/csrf-token', (req, res) => {
  const token = crypto.randomBytes(32).toString('hex')
  res.cookie('csrf-token', token, {
    httpOnly: false,  // must be accessible by JS
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'strict',
  })
  res.json({ token })
})
```

#### Helmet.js Configuration

```ts
import helmet from 'helmet'

// Production-grade helmet configuration
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      scriptSrc: ["'self'", "'unsafe-inline'"],  // adjust for your frontend framework
      styleSrc: ["'self'", "'unsafe-inline'"],
      imgSrc: ["'self'", 'data:', 'https:'],
      connectSrc: ["'self'", process.env.API_URL!].filter(Boolean),
      fontSrc: ["'self'", 'https://fonts.gstatic.com'],
      objectSrc: ["'none'"],
      frameAncestors: ["'none'"],
    },
  },
  crossOriginEmbedderPolicy: false,  // set true if using SharedArrayBuffer
  crossOriginResourcePolicy: { policy: 'same-origin' },
  dnsPrefetchControl: { allow: false },
  frameguard: { action: 'deny' },
  hidePoweredBy: true,
  hsts: { maxAge: 31536000, includeSubDomains: true, preload: true },
  ieNoOpen: true,
  noSniff: true,
  referrerPolicy: { policy: 'strict-origin-when-cross-origin' },
  xssFilter: true,
}))
```

#### Secrets Management

```ts
// src/config/index.ts
import { z } from 'zod'
import { config } from 'dotenv'

config()  // load .env file

const envSchema = z.object({
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  PORT: z.coerce.number().int().positive().default(3000),
  DATABASE_URL: z.string().url(),
  REDIS_URL: z.string().url(),
  JWT_ACCESS_SECRET: z.string().min(32),
  JWT_REFRESH_SECRET: z.string().min(32),
  CORS_ORIGIN: z.string().default('http://localhost:3000'),
  SENTRY_DSN: z.string().url().optional(),
  SMTP_HOST: z.string().optional(),
  SMTP_PORT: z.coerce.number().optional(),
  AWS_ACCESS_KEY_ID: z.string().optional(),
  AWS_SECRET_ACCESS_KEY: z.string().optional(),
})

const parsed = envSchema.safeParse(process.env)

if (!parsed.success) {
  console.error('Invalid environment variables:', parsed.error.flatten().fieldErrors)
  process.exit(1)
}

export const env = parsed.data
```

---

### Performance Optimization

#### Clustering

```ts
// src/cluster.ts — PM2 alternative with built-in cluster module
import cluster from 'node:cluster'
import { cpus } from 'node:os'
import { createApp } from './app'
import { logger } from './lib/logger'

const PORT = parseInt(process.env.PORT ?? '3000', 10)
const WORKERS = parseInt(process.env.WORKERS ?? String(cpus().length), 10)

if (cluster.isPrimary) {
  logger.info({ workers: WORKERS, port: PORT }, 'Primary process starting workers')

  // Fork workers
  for (let i = 0; i < WORKERS; i++) cluster.fork()

  // Restart dead workers
  cluster.on('exit', (worker, code, signal) => {
    logger.warn({ pid: worker.process.pid, code, signal }, 'Worker died, restarting')
    cluster.fork()
  })
} else {
  const app = createApp()

  app.listen(PORT, () => {
    logger.info({ pid: process.pid, port: PORT }, 'Worker started')
  })
}
```

```ini
# ecosystem.config.js (PM2)
module.exports = {
  apps: [{
    name: 'my-api',
    script: 'dist/server.js',
    instances: 'max',           // use all CPU cores
    exec_mode: 'cluster',
    env: { NODE_ENV: 'production' },
    max_memory_restart: '500M',
    log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
    error_file: './logs/err.log',
    out_file: './logs/out.log',
    merge_logs: true,
    autorestart: true,
    watch: false,
    max_restarts: 10,
    restart_delay: 4000,
  }]
}
```

#### Response Caching Strategies

```ts
// HTTP Cache Headers (for GET endpoints)
router.get('/users/:id', asyncWrap(async (req, res) => {
  const user = await findUserById(req.params.id)
  if (!user) throw new NotFoundError('User', req.params.id)

  // Cache for 60 seconds, stale-while-revalidate for 300 seconds
  res.set('Cache-Control', 'public, max-age=60, stale-while-revalidate=300')
  res.json(success(user))
}))

// Redis cache layer
import { createClient } from 'redis'

const cache = createClient({ url: process.env.REDIS_URL })
await cache.connect()

async function getOrSet<T>(key: string, fetch: () => Promise<T>, ttl = 60): Promise<T> {
  const cached = await cache.get(key)
  if (cached) return JSON.parse(cached)

  const data = await fetch()
  await cache.setEx(key, ttl, JSON.stringify(data))
  return data
}

// Usage
router.get('/users', asyncWrap(async (req, res) => {
  const users = await getOrSet('users:all', () => db.user.findMany(), 30)
  res.json(success(users))
}))

// Cache invalidation on write
router.post('/users', validate(createUserSchema), asyncWrap(async (req, res) => {
  const user = await createUser(req.body)
  await cache.del('users:all')  // invalidate list cache
  res.status(201).json(success(user))
}))
```

#### N+1 Query Prevention

```ts
// ❌ BAD: N+1 — fetches author for EACH post
const posts = await db.post.findMany()
for (const post of posts) {
  const author = await db.user.findUnique({ where: { id: post.authorId } })
  // ...
}

// ✅ GOOD: Eager loading with Prisma `include`
const posts = await db.post.findMany({
  include: { author: { select: { id: true, name: true, email: true } } },
})

// ✅ GOOD: Batch loading with DataLoader
import DataLoader from 'dataloader'

const userLoader = new DataLoader(async (ids: string[]) => {
  const users = await db.user.findMany({ where: { id: { in: ids } } })
  const userMap = new Map(users.map(u => [u.id, u]))
  return ids.map(id => userMap.get(id) ?? null)
})

// In handler:
const author = await userLoader.load(post.authorId)  // batched!
```

#### Memory Leak Detection

```ts
// src/lib/heapdump.ts
import heapdump from 'heapdump'

// Trigger heap dump on SIGUSR2
process.on('SIGUSR2', () => {
  const filename = `heap-${new Date().toISOString()}.heapsnapshot`
  heapdump.writeSnapshot(filename, (err) => {
    if (err) logger.error({ err }, 'Heap dump failed')
    else logger.info({ filename }, 'Heap dump written')
  })
})

// Auto heap dump on high memory usage
setInterval(() => {
  const usage = process.memoryUsage()
  if (usage.heapUsed > 500 * 1024 * 1024) {  // 500MB
    logger.warn({ heapUsed: usage.heapUsed }, 'High memory usage detected')
    const filename = `heap-auto-${Date.now()}.heapsnapshot`
    heapdump.writeSnapshot(filename)
  }
}, 60_000)
```

```bash
# Clinic.js profiling
# npm install -g clinic

# Flame graph (CPU profiling)
clinic flame -- node dist/server.js

# Doctor (general health check)
clinic doctor -- node dist/server.js

# Bubbleprof (async I/O visualization)
clinic bubbleprof -- node dist/server.js

# 0x profiler
# npm install -g 0x
0x -o dist/server.js
```

---

### Logging & Observability

#### Structured Logging with Pino

```ts
// src/lib/logger.ts
import pino from 'pino'
import { randomUUID } from 'node:crypto'
import { AsyncLocalStorage } from 'node:async_hooks'

// Request context for correlation IDs
export const requestContext = new AsyncLocalStorage<{ requestId: string }>()

export const logger = pino({
  level: process.env.LOG_LEVEL ?? 'info',
  transport: process.env.NODE_ENV === 'development'
    ? { target: 'pino-pretty', options: { colorize: true, translateTime: 'SYS:standard' } }
    : undefined,
  serializers: {
    err: pino.stdSerializers.err,
    req: pino.stdSerializers.req,
    res: pino.stdSerializers.res,
  },
  redact: ['req.headers.authorization', 'req.headers.cookie', 'password', 'token'],
})

// Middleware to set request context
import type { Request, Response, NextFunction } from 'express'

export function requestContextMiddleware(req: Request, _res: Response, next: NextFunction) {
  const requestId = req.requestId
  requestContext.run({ requestId }, () => {
    childLogger = logger.child({ requestId })
    next()
  })
}

// Usage: import { logger } and add context anywhere
function getUserLogger() {
  const ctx = requestContext.getStore()
  return ctx ? logger.child({ requestId: ctx.requestId }) : logger
}
```

#### Winston Alternative

```ts
// src/lib/winston-logger.ts
import winston from 'winston'

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL ?? 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    process.env.NODE_ENV === 'production'
      ? winston.format.json()
      : winston.format.prettyPrint({ colorize: true }),
  ),
  defaultMeta: { service: 'my-api' },
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'logs/error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/combined.log' }),
  ],
})
```

#### OpenTelemetry Integration

```ts
// src/lib/telemetry.ts
import { NodeSDK } from '@opentelemetry/sdk-node'
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http'
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http'
import { ExpressInstrumentation } from '@opentelemetry/instrumentation-express'
import { PgInstrumentation } from '@opentelemetry/instrumentation-pg'
import { Resource } from '@opentelemetry/resources'
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions'

export function initTelemetry() {
  if (!process.env.OTEL_EXPORTER_OTLP_ENDPOINT) return

  const sdk = new NodeSDK({
    resource: new Resource({
      [SemanticResourceAttributes.SERVICE_NAME]: 'my-api',
      [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
    }),
    traceExporter: new OTLPTraceExporter(),
    instrumentations: [
      new HttpInstrumentation(),
      new ExpressInstrumentation(),
      new PgInstrumentation(),
    ],
  })

  sdk.start()

  // Graceful shutdown
  process.on('SIGTERM', () => sdk.shutdown())
}
```

#### Health Check Endpoints

```ts
// src/routes/health.ts
import { Router } from 'express'
import { pool } from '../db/pool'
import { createClient } from 'redis'

const router = Router()

// Basic health check
router.get('/health', (_req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  })
})

// Readiness check (verifies dependencies)
router.get('/ready', async (_req, res) => {
  const checks = {
    database: false,
    redis: false,
  }

  try {
    await pool.query('SELECT 1')
    checks.database = true
  } catch {
    // database down
  }

  try {
    const redis = createClient({ url: process.env.REDIS_URL })
    await redis.connect()
    await redis.ping()
    await redis.disconnect()
    checks.redis = true
  } catch {
    // redis down
  }

  const allHealthy = Object.values(checks).every(Boolean)

  res.status(allHealthy ? 200 : 503).json({
    status: allHealthy ? 'ok' : 'degraded',
    checks,
    timestamp: new Date().toISOString(),
  })
})

export { router as healthRouter }
```

#### Graceful Shutdown

```ts
// src/shutdown.ts
import type { Server } from 'node:http'
import { logger } from './lib/logger'
import { prisma } from './lib/prisma'
import { pool } from './db/pool'
import { io } from './lib/socket'

interface ShutdownDeps {
  httpServer: Server
  redis?: { disconnect: () => Promise<void> }
}

export function setupGracefulShutdown(deps: ShutdownDeps) {
  const shutdown = async (signal: string) => {
    logger.info({ signal }, 'Shutting down gracefully...')

    // 1. Stop accepting new connections
    deps.httpServer.close(() => {
      logger.info('HTTP server closed')
    })

    // 2. Close WebSocket connections
    if (io) {
      io.close(() => logger.info('WebSocket server closed'))
    }

    // 3. Disconnect database
    await prisma.$disconnect().catch(() => {})
    await pool.end().catch(() => {})

    // 4. Disconnect Redis
    if (deps.redis) {
      await deps.redis.disconnect().catch(() => {})
    }

    logger.info('All connections closed, exiting')
    process.exit(0)
  }

  // Force shutdown after timeout
  const forceShutdown = (signal: string) => {
    logger.error({ signal }, 'Forced shutdown after timeout')
    process.exit(1)
  }

  process.on('SIGTERM', () => {
    shutdown('SIGTERM')
    setTimeout(() => forceShutdown('SIGTERM'), 10_000).unref()
  })

  process.on('SIGINT', () => {
    shutdown('SIGINT')
    setTimeout(() => forceShutdown('SIGINT'), 10_000).unref()
  })
}
```

---

### Project Structure

#### Modular Monolith Structure

```
src/
├── config/               # Environment configuration, Zod schema
│   └── index.ts
├── lib/                  # Shared utilities, helpers
│   ├── errors.ts         # Custom error classes
│   ├── logger.ts         # Pino/Winston logger
│   ├── jwt.ts            # JWT sign/verify
│   ├── response.ts       # Standardized response helpers
│   ├── events.ts         # Application EventEmitter
│   └── async-wrap.ts     # Express error wrapper
├── middleware/            # Global middleware
│   ├── auth.ts
│   ├── error-handler.ts
│   ├── request-id.ts
│   ├── validate.ts
│   ├── rate-limiter.ts
│   └── csrf.ts
├── modules/              # Feature modules (vertical slices)
│   ├── users/
│   │   ├── users.controller.ts
│   │   ├── users.service.ts
│   │   ├── users.routes.ts
│   │   ├── users.repository.ts
│   │   ├── users.validation.ts
│   │   ├── users.test.ts
│   │   └── index.ts
│   ├── auth/
│   │   ├── auth.controller.ts
│   │   ├── auth.service.ts
│   │   ├── auth.routes.ts
│   │   ├── strategies/        # Passport strategies
│   │   ├── guards/            # Auth guards
│   │   └── index.ts
│   └── posts/
│       └── ...
├── db/                   # Database layer
│   ├── migrations/
│   ├── seeds/
│   ├── pool.ts           # pg Pool instance
│   └── queries/          # Raw SQL queries if not using ORM
├── workers/              # Background job processors
│   ├── email-worker.ts
│   └── report-worker.ts
├── app.ts                # Express app factory
├── server.ts             # Entry point
├── cluster.ts            # Cluster mode
└── test/                 # Test utilities
    ├── setup.ts
    ├── factories.ts
    └── helpers.ts
```

#### Nest.js Project Structure

```
src/
├── main.ts                       # Entry point
├── app.module.ts                 # Root module
├── common/                       # Cross-cutting concerns
│   ├── decorators/
│   │   ├── roles.decorator.ts
│   │   └── public.decorator.ts
│   ├── filters/
│   │   └── http-exception.filter.ts
│   ├── guards/
│   │   ├── jwt-auth.guard.ts
│   │   └── roles.guard.ts
│   ├── interceptors/
│   │   └── transform.interceptor.ts
│   ├── pipes/
│   │   └── validation.pipe.ts
│   └── dto/
│       └── pagination.dto.ts
├── config/                       # Configuration
│   ├── config.module.ts
│   ├── config.service.ts
│   └── schema.ts
├── modules/                      # Feature modules
│   ├── users/
│   │   ├── users.module.ts
│   │   ├── users.controller.ts
│   │   ├── users.service.ts
│   │   ├── dto/
│   │   │   ├── create-user.dto.ts
│   │   │   └── update-user.dto.ts
│   │   ├── entities/
│   │   │   └── user.entity.ts
│   │   └── users.service.spec.ts
│   └── auth/
│       └── ...
├── prisma/
│   ├── prisma.module.ts
│   ├── prisma.service.ts
│   └── schema.prisma
└── database/
    ├── migrations/
    └── seeds/
```

#### Clean Architecture / Hexagonal Structure

```
src/
├── domain/               # Enterprise business rules (pure TS, no framework deps)
│   ├── entities/
│   │   └── user.ts
│   ├── value-objects/
│   │   └── email.ts
│   ├── ports/            # Interfaces for external dependencies
│   │   ├── user-repository.port.ts
│   │   └── email-service.port.ts
│   └── use-cases/        # Application business rules
│       ├── create-user.usecase.ts
│       └── get-user.usecase.ts
├── infrastructure/       # Adapter implementations
│   ├── repositories/
│   │   └── prisma-user.repository.ts
│   ├── services/
│   │   └── smtp-email.service.ts
│   └── database/
│       └── prisma.ts
├── api/                  # HTTP layer (Express/Nest/Fastify)
│   ├── controllers/
│   ├── middleware/
│   ├── dto/
│   └── routes/
├── config/
└── server.ts
```

---

### File Convention

```
Supported frameworks: Express.js, Fastify, Nest.js
Language: TypeScript (strict mode)
Testing: Vitest
Package manager: pnpm (preferred), npm, yarn
Format: Prettier + ESLint
```

#### Naming Rules

```
Files:
  Controllers:     kebab-case — users.controller.ts
  Services:        kebab-case — users.service.ts
  Routes:          kebab-case — users.routes.ts
  Middleware:      kebab-case — error-handler.ts
  Entities/Models: kebab-case — user.entity.ts
  DTOs:            kebab-case — create-user.dto.ts
  Tests:           co-locate — users.controller.spec.ts
  Factories:       kebab-case — user.factory.ts
  Constants:       kebab-case — auth.constants.ts
  Interfaces:      PascalCase — IUserService.ts (or UserService.ts as interface)
  Types:           PascalCase — PaginatedResult.ts
  Enums:           PascalCase — UserRole.ts

Directories:
  Feature modules: singular nouns — user/, auth/, order/
  Shared:          kebab-case — common/, shared/, lib/, middleware/
  Test:            kebab-case — test/, __tests__/
  Database:        db/, database/, prisma/

Exports:
  Default export for main module, named exports for everything else
  Barrel files: index.ts re-exports module contents

Conventions:
  Imports: relative paths within module, absolute paths for cross-module
  Max line length: 100 characters
  Semicolons: required
  Single quotes: preferred
  Trailing commas: always
  Functions: arrow functions for callbacks, function keyword for top-level
  Async: async/await over .then().catch()
```

---

### Anti-Patterns (with Fixes)

#### 1. Callback Hell → Async/Await

```ts
// ❌ BAD: callback hell (Express 3 / legacy)
app.get('/users/:id', (req, res) => {
  db.query('SELECT * FROM users WHERE id = $1', [req.params.id], (err, result) => {
    if (err) return res.status(500).json({ error: err.message })
    db.query('SELECT * FROM posts WHERE author_id = $1', [req.params.id], (err2, posts) => {
      if (err2) return res.status(500).json({ error: err2.message })
      res.json({ user: result.rows[0], posts: posts.rows })
    })
  })
})

// ✅ GOOD: async/await with proper error handling
router.get('/users/:id', asyncWrap(async (req, res) => {
  const [user, posts] = await Promise.all([
    pool.query('SELECT * FROM users WHERE id = $1', [req.params.id]).then(r => r.rows[0]),
    pool.query('SELECT * FROM posts WHERE author_id = $1', [req.params.id]).then(r => r.rows),
  ])
  if (!user) throw new NotFoundError('User', req.params.id)
  res.json(success({ user, posts }))
}))
```

#### 2. Uncaught Promise Rejections

```ts
// ❌ BAD: silent promise rejection
function processData(id: string) {
  db.query('UPDATE users SET status = $1 WHERE id = $2', ['processed', id])
  // If this fails, nothing catches it
}

// ✅ GOOD: process-level handler + explicit catches
process.on('unhandledRejection', (reason) => {
  logger.error({ err: reason }, 'Unhandled Rejection — this should never happen')
})

function processData(id: string) {
  db.query('UPDATE users SET status = $1 WHERE id = $2', ['processed', id])
    .catch(err => logger.error({ id, err }, 'Failed to process user'))
}
```

#### 3. Synchronous Error Handler without Async Support

```ts
// ❌ BAD: Express doesn't catch async errors automatically
router.get('/users/:id', async (req, res) => {
  const user = await db.user.findUnique({ where: { id: req.params.id } })
  if (!user) throw new NotFoundError('User', req.params.id)  // Unhandled!
  res.json(user)
})
// Express will crash: UnhandledPromiseRejection

// ✅ GOOD: wrap with async error handler
router.get('/users/:id', asyncWrap(async (req, res) => {
  const user = await db.user.findUnique({ where: { id: req.params.id } })
  if (!user) throw new NotFoundError('User', req.params.id)
  res.json(user)
}))
// Or use: import 'express-async-errors' (patches Express)
```

#### 4. Exposing Stack Traces in Production

```ts
// ❌ BAD: exposes internal file paths and line numbers
function errorHandler(err: Error, _req: Request, res: Response) {
  res.status(500).json({ error: err.stack })
  // Response: "Error: Something broke\n    at Object.<anonymous> (/var/www/app/src/controllers/user.ts:42:7)"
}

// ✅ GOOD: safe error response
function errorHandler(err: Error, req: Request, res: Response) {
  const statusCode = err instanceof AppError ? err.statusCode : 500
  logger.error({ err: err.stack, requestId: req.requestId })

  res.status(statusCode).json({
    success: false,
    error: {
      code: err instanceof AppError ? err.code : 'INTERNAL_ERROR',
      message: process.env.NODE_ENV === 'production'
        ? 'An unexpected error occurred'
        : err.message,
      timestamp: new Date().toISOString(),
      requestId: req.requestId,
    },
  })
}
```

#### 5. Magic Strings → Constants/Enums

```ts
// ❌ BAD: magic strings scattered across codebase
if (user.role === 'admin') { /* ... */ }
res.status(404).json({ error: 'user not found' })
cacheKey = `user:${id}:profile`

// ✅ GOOD: constants and enums
// src/modules/users/users.constants.ts
export const UserRole = {
  ADMIN: 'admin',
  USER: 'user',
  MODERATOR: 'moderator',
} as const

export const CacheKeys = {
  userProfile: (id: string) => `user:${id}:profile`,
  userList: 'users:all',
} as const

export const ErrorCodes = {
  NOT_FOUND: 'NOT_FOUND',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
  RATE_LIMIT: 'RATE_LIMIT',
} as const

// Usage:
if (user.role === UserRole.ADMIN) { /* ... */ }
throw new NotFoundError('User')
await cache.get(CacheKeys.userProfile(id))
```

#### 6. God Middleware → Single Responsibility

```ts
// ❌ BAD: middleware doing everything
router.use(async (req, res, next) => {
  // Logs request
  console.log(`${req.method} ${req.path}`)
  // Checks auth
  const token = req.headers.authorization
  if (token) {
    try {
      req.user = jwt.verify(token, SECRET)
    } catch {
      return res.status(401).json({ error: 'unauthorized' })
    }
  }
  // Rate limits
  const ip = req.ip
  const count = await redis.incr(`rate:${ip}`)
  if (count > 100) return res.status(429).json({ error: 'rate limit' })
  // Measures latency
  const start = Date.now()
  res.on('finish', () => console.log(`${req.path} took ${Date.now() - start}ms`))
  next()
})

// ✅ GOOD: each middleware has ONE responsibility
router.use(requestLogger)
router.use(authenticate)       // only sets req.user, never returns error
router.use(rateLimiter)
router.use(latencyTracker)
```

#### 7. Blocking the Event Loop

```ts
// ❌ BAD: CPU-intensive operation blocks event loop
import { createHash } from 'node:crypto'

function hashPassword(password: string, iterations = 100_000): string {
  let hash = password
  for (let i = 0; i < iterations; i++) {
    hash = createHash('sha256').update(hash).digest('hex')
  }
  return hash
}
// This blocks ALL OTHER requests for seconds

// ✅ GOOD: use bcrypt (which uses native code) or worker threads
import bcrypt from 'bcrypt'
const hash = await bcrypt.hash(password, 12)  // non-blocking, async

// ✅ GOOD: for custom CPU work, use worker threads
import { Worker } from 'node:worker_threads'
const result = await runInWorker('./hash-worker.js', { password, iterations: 100_000 })
```

#### 8. Ignoring `max_body_size`

```ts
// ❌ BAD: no body size limit — attacker can send 1GB JSON
app.use(express.json())

// ✅ GOOD: limit body size
app.use(express.json({ limit: '10kb' }))
app.use(express.urlencoded({ extended: true, limit: '10kb' }))
// Large payloads: 1MB for file uploads via multer with size validation
```

---

### Implementation Checklist

**Architecture Phase**:
- [ ] Framework selected based on decision tree (Express/Fastify/Nest.js)
- [ ] Project structure: modular monolith or clean architecture
- [ ] Database strategy: ORM (Prisma/Drizzle) vs Query Builder vs Raw SQL
- [ ] Error handling: custom error classes + global error handler
- [ ] Standardized response format: { success, data, error, meta, timestamp }
- [ ] Environment configuration with Zod validation

**Development Phase**:
- [ ] TypeScript strict mode enabled (no `any`, strictNullChecks, noImplicitAny)
- [ ] Request validation with Zod/Joi (whitelist approach)
- [ ] Authentication: JWT with access + refresh token rotation
- [ ] Authorization: RBAC middleware on protected routes
- [ ] Request ID middleware for correlation
- [ ] Structured logging (Pino recommended)
- [ ] Rate limiting on all endpoints (stricter on auth)
- [ ] CORS configured for known origins
- [ ] Helmet.js with production CSP
- [ ] Body size limits (10kb default)
- [ ] API versioning established (URL-based v1)

**Performance Phase**:
- [ ] Connection pooling configured (pg pool max = 20)
- [ ] No N+1 queries (eager loading, DataLoader, batch queries)
- [ ] Response caching (HTTP headers + Redis)
- [ ] Compression middleware (gzip level 6)
- [ ] PM2 cluster mode or Node.js cluster module
- [ ] Database indexes on all query columns
- [ ] Query timeout (statement_timeout = 30s)
- [ ] Memory limit (PM2 max_memory_restart = 500M)

**Testing Phase**:
- [ ] Vitest configured with globals and coverage thresholds
- [ ] Unit tests for services (mocked dependencies)
- [ ] Integration tests for API endpoints (supertest)
- [ ] Auth endpoint tests (valid token, expired, missing, invalid)
- [ ] Error path tests (404, 400, 401, 403, 429, 500)
- [ ] Test factories with faker.js
- [ ] Database tests with testcontainers or transaction rollback
- [ ] E2E tests for critical user journeys (Playwright)

**Security Phase**:
- [ ] SQL injection prevention (parameterized queries everywhere)
- [ ] XSS prevention (helmet CSP, output encoding)
- [ ] CSRF protection (SameSite cookies, double-submit for session auth)
- [ ] Rate limiting (15 min window, 100 global / 5 auth)
- [ ] Input validation (whitelist, reject unknown fields)
- [ ] No secrets in code (dotenv + Zod schema)
- [ ] npm audit in CI pipeline
- [ ] Dependabot/Renovate for automated updates
- [ ] HTTP redirect to HTTPS in production
- [ ] stack traces hidden in production errors

**Deployment Phase**:
- [ ] Dockerfile with multi-stage build
- [ ] Health check endpoints (/health, /ready)
- [ ] Graceful shutdown (SIGTERM handler)
- [ ] Structured logging JSON format
- [ ] OpenTelemetry instrumentation
- [ ] Error monitoring (Sentry)
- [ ] Process manager (PM2 for Node.js)
- [ ] Database migration strategy (automatic in CI, manual for production)
- [ ] Feature flags for gradual rollout
- [ ] Backup and rollback plan

---

### Common Troubleshooting

#### "ECONNRESET / socket hang up"

```
Cause: Client disconnected before response was sent.
Common scenarios:
  - Client timeout shorter than server processing time
  - Proxy (nginx, Cloudflare) timeout
  - Server under heavy load causing response delays

Solution:
  - Increase timeout in proxy config:
    proxy_read_timeout 60s;
    proxy_send_timeout 60s;
  - Use async handlers (don't block event loop)
  - Add connection keep-alive:
    agent: new http.Agent({ keepAlive: true })
  - Catch ECONNRESET in stream error handlers
```

#### "Process out of memory"

```
Cause: Memory leak or excessive memory usage.

Diagnose:
  1. Check heap snapshot (heapdump)
  2. Check memory timeline (clinic.js doctor)
  3. Look for:
     - Growing arrays/maps (caching without eviction)
     - Event listeners without removal
     - Closure capturing large objects
     - Streams not consumed/destroyed

Common fixes:
  - Add TTL to all caches (Redis: expire, in-memory: Map with cleanup)
  - Use WeakRef / FinalizationRegistry for disposable objects
  - Set stream highWaterMark limits
  - Unref timers and connections
  - Limit array/query result sizes
```

#### "ETIMEOUT — database query hangs"

```
Cause: Long-running query blocking connection pool.

Solution:
  1. Set statement_timeout at pool level:
     new Pool({ connectionString: DATABASE_URL, statement_timeout: 30_000 })

  2. Check for missing indexes:
     EXPLAIN ANALYZE SELECT * FROM users WHERE email = 'test@test.com';

  3. Monitor pg_stat_activity for stuck queries:
     SELECT pid, query, state, wait_event FROM pg_stat_activity
     WHERE state != 'idle' AND query NOT LIKE '%pg_stat%';

  4. Reduce query complexity:
     - Add LIMIT to all queries
     - Paginate instead of loading all
     - Use SELECT only needed columns
```

#### "Port 3000 already in use"

```bash
# Find what's using the port
netstat -ano | findstr :3000

# Kill the process (Windows)
taskkill /PID <PID> /F

# Kill the process (Linux/Mac)
kill -9 $(lsof -t -i:3000)

# Better: use port fallback
const PORT = process.env.PORT ?? 3000
const server = app.listen(PORT, () => {
  logger.info({ port: server.address().port }, 'Server started')
})
```

#### "Module not found / Cannot find module"

```
Root causes:
  - Missing dependency (npm install)
  - Wrong import path
  - Package not in dependencies (devDependencies vs dependencies)
  - Missing tsconfig paths alias registration

Diagnose:
  - Check package.json: is it in dependencies or devDependencies?
  - Check tsconfig.json: paths alias maps to actual directory
  - Run: node -e "require('module-name')" to test resolution
  - Run: npm ls module-name to check version/installation

Common fix: path alias in tsconfig.json
{
  "compilerOptions": {
    "paths": {
      "@/*": ["./src/*"]
    }
  }
}
```

#### "Prisma: Invalid `prisma.user.findUnique()` invocation"

```
Cause: Schema mismatch between Prisma client and database.

Fix:
  1. Regenerate Prisma client:
     npx prisma generate

  2. Run pending migrations:
     npx prisma migrate deploy

  3. Reset database in development:
     npx prisma migrate reset

Prevention:
  - Add prisma generate to CI pipeline
  - Run prisma migrate deploy in pre-start script
  - Version control Prisma schema file
```

#### "bcrypt always returns false"

```ts
// ❌ BAD: comparing against wrong hash format
const isValid = await bcrypt.compare(password, hashedPassword)
// Returns false even when password is correct!

// ✅ GOOD: check that both arguments are correct:
// 1. password: plain text string
// 2. hashedPassword: string starting with $2b$ or $2a$

// Verify hash format:
console.log(hashedPassword.startsWith('$2'))  // should be true
console.log(typeof password)                   // should be string

// Common mistake — comparing against another hash instead of plain text
// ❌ bcrypt.compare(hash1, hash2)  — comparing two hashes!
```

#### "Socket.io connection fails"

```
Cause: CORS misconfiguration or protocol mismatch.

Check:
  1. Client URL matches CORS origin in server config
  2. Client uses correct transport (websocket vs polling)
  3. Proxy (nginx) configured for WebSocket:
     proxy_set_header Upgrade $http_upgrade;
     proxy_set_header Connection "upgrade";

Solution:
  // Server
  io = new Server(httpServer, {
    cors: {
      origin: process.env.CLIENT_URL,
      credentials: true,
    },
    transports: ['websocket', 'polling'],  // polling as fallback
  })

  // Client
  const socket = io(SERVER_URL, {
    withCredentials: true,
    transports: ['websocket'],
  })
```

#### "Nest.js: Circular dependency between modules"

```
Error: Nest cannot create the module instance.
A circular dependency was detected.

Fix:
  // Use forwardRef() to break the cycle
  @Module({
    imports: [forwardRef(() => OtherModule)],
  })
  export class CurrentModule {}

  @Injectable()
  export class MyService {
    constructor(
      @Inject(forwardRef(() => OtherService))
      private otherService: OtherService,
    ) {}
  }

Better: Restructure modules to eliminate circular dependency.
  - Extract shared dependency into a separate module
  - Use a shared module with common exports
```
