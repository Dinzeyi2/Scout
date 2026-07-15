export type StartupType = "software" | "physical" | "hybrid";
export type SignalKind =
  | "engineering"
  | "infrastructure"
  | "product"
  | "customer"
  | "operations"
  | "manufacturing"
  | "compliance"
  | "revenue";
export type VerificationStatus = "verified" | "attested" | "self_reported" | "inferred" | "unverified";

export interface ScoutOptions {
  apiKey: string;
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export interface AutoMonitorOptions {
  serviceName?: string;
  environment?: string;
  heartbeatIntervalMs?: number;
  captureErrors?: boolean;
  metadata?: Record<string, unknown>;
}

export interface SignalInput {
  kind: SignalKind;
  source: string;
  name: string;
  value: number;
  unit?: string;
  occurred_at?: string;
  observed_at?: string;
  verification_status?: VerificationStatus;
  source_event_id?: string;
  metadata?: Record<string, unknown>;
}

export interface StartupCreate {
  name: string;
  type?: StartupType;
  website?: string;
  api_key_name?: string;
}

export interface StartupCreated {
  id: number;
  name: string;
  api_key: string;
  api_key_prefix: string;
}

export interface GitHubRepositoryInput {
  owner: string;
  repo: string;
  branch?: string;
}

export class ScoutApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly details: unknown,
  ) {
    super(message);
    this.name = "ScoutApiError";
  }
}

export class Scout {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ScoutOptions) {
    if (!options.apiKey) {
      throw new Error("Scout apiKey is required. Store it in a server-side environment variable.");
    }
    this.apiKey = options.apiKey;
    this.baseUrl = (options.baseUrl ?? "https://your-scout-api.up.railway.app").replace(/\/$/, "");
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  static fromEnv(env: Record<string, string | undefined> = processEnv()): Scout {
    return new Scout({
      apiKey: env.SCOUT_API_KEY ?? "",
      baseUrl: env.SCOUT_BASE_URL,
    });
  }

  static monitor(options: AutoMonitorOptions = {}, env: Record<string, string | undefined> = processEnv()): Scout {
    const scout = Scout.fromEnv(env);
    scout.startMonitoring(options, env);
    return scout;
  }

  startMonitoring(options: AutoMonitorOptions = {}, env: Record<string, string | undefined> = processEnv()): void {
    const serviceName = options.serviceName ?? env.SERVICE_NAME ?? env.RAILWAY_SERVICE_NAME ?? "app";
    const environment = options.environment ?? env.NODE_ENV ?? env.RAILWAY_ENVIRONMENT_NAME ?? "unknown";
    const metadata = {
      service_name: serviceName,
      environment,
      railway_service_id: env.RAILWAY_SERVICE_ID,
      railway_environment_id: env.RAILWAY_ENVIRONMENT_ID,
      ...options.metadata,
    };

    void this.track({
      kind: "infrastructure",
      source: "scout_sdk",
      name: "application_started",
      value: 1,
      unit: "event",
      verification_status: "attested",
      source_event_id: `scout-sdk-start-${Date.now()}`,
      metadata,
    }).catch(() => undefined);

    const intervalMs = options.heartbeatIntervalMs ?? 60_000;
    if (intervalMs > 0) {
      setInterval(() => {
        void this.track({
          kind: "infrastructure",
          source: "scout_sdk",
          name: "application_heartbeat",
          value: 1,
          unit: "heartbeat",
          verification_status: "attested",
          source_event_id: `scout-sdk-heartbeat-${Date.now()}`,
          metadata,
        }).catch(() => undefined);
      }, intervalMs);
    }

    if (options.captureErrors ?? true) {
      const proc = processObject();
      proc?.on?.("uncaughtException", (error: unknown) => {
        void this.captureError(error, { ...metadata, error_type: "uncaughtException" });
      });
      proc?.on?.("unhandledRejection", (error: unknown) => {
        void this.captureError(error, { ...metadata, error_type: "unhandledRejection" });
      });
    }
  }

  async track(signal: SignalInput): Promise<unknown> {
    return this.request("/v1/signals", {
      method: "POST",
      body: JSON.stringify({ unit: "count", verification_status: "self_reported", metadata: {}, ...signal }),
    });
  }

  async trackMany(signals: SignalInput[]): Promise<unknown[]> {
    return Promise.all(signals.map((signal) => this.track(signal)));
  }

  async captureError(error: unknown, metadata: Record<string, unknown> = {}): Promise<unknown> {
    const message = error instanceof Error ? error.message : String(error);
    const stack = error instanceof Error ? error.stack : undefined;
    return this.track({
      kind: "infrastructure",
      source: "scout_sdk",
      name: "application_error",
      value: 1,
      unit: "error",
      verification_status: "attested",
      source_event_id: `scout-sdk-error-${Date.now()}`,
      metadata: { message, stack, ...metadata },
    });
  }

  async connectGitHubRepository(input: GitHubRepositoryInput): Promise<unknown> {
    return this.request("/v1/connectors/github/public-repository", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async founderDashboard<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/founder-dashboard");
  }

  async investorDashboard<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/investor-dashboard");
  }

  async investorReport<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/investor-report");
  }

  async executionNarrative<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/execution-narrative");
  }

  async evidenceTimeline<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/evidence-timeline");
  }

  async auditLogs<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/security/audit-logs");
  }

  async dataInventory<T = unknown>(): Promise<T> {
    return this.request<T>("/v1/security/data-inventory");
  }

  private async request<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${this.apiKey}`,
        ...(init.headers ?? {}),
      },
    });

    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) {
      throw new ScoutApiError(`Scout API request failed with ${response.status}`, response.status, payload);
    }
    return payload as T;
  }
}

export async function createStartup(baseUrl: string, payload: StartupCreate): Promise<StartupCreated> {
  const response = await fetch(`${baseUrl.replace(/\/$/, "")}/v1/startups`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: "software", api_key_name: "default", ...payload }),
  });
  const body = await response.json();
  if (!response.ok) {
    throw new ScoutApiError(`Scout startup creation failed with ${response.status}`, response.status, body);
  }
  return body as StartupCreated;
}

function processEnv(): Record<string, string | undefined> {
  try {
    return (globalThis as unknown as { process?: { env?: Record<string, string | undefined> } }).process?.env ?? {};
  } catch {
    return {};
  }
}

function processObject(): { on?: (event: string, handler: (error: unknown) => void) => void } | undefined {
  return (globalThis as unknown as { process?: { on?: (event: string, handler: (error: unknown) => void) => void } }).process;
}
