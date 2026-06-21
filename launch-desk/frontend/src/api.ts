import type { Appointment, AuditEntry, Invoice, LoginRequest, Paginated, Patient, Role, Task, TreatmentPlan, User, QueueJob } from './types';

type ApiError = { error: { code: string; message: string; details?: unknown } };

const baseFetch = async (input: RequestInfo, init: RequestInit = {}) => {
  const response = await fetch(input, init);
  const payload = (await response.json()) as unknown;
  if (!response.ok) {
    const error = payload as ApiError;
    throw new Error(error.error?.message || `Request failed: ${response.status}`);
  }
  return payload as unknown;
};

export class ApiClient {
  constructor(private readonly token: string | null) {}

  private authHeaders = (): HeadersInit => {
    return this.token ? { Authorization: `Bearer ${this.token}` } : {};
  };

  login = async (input: LoginRequest) => {
    return baseFetch('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(input),
    }) as Promise<{ token: string; expiresAt: number; user: User }>;
  };

  me = async () => {
    return baseFetch('/api/auth/me', {
      headers: { ...this.authHeaders() },
    }) as Promise<{ user: User }>;
  };

  dashboard = async () => {
    return baseFetch('/api/dashboard', {
      headers: { ...this.authHeaders() },
    }) as Promise<{ summary: { todayAppointments: number; pendingTasks: number; openInvoices: number }; recentAudit: AuditEntry[] }>;
  };

  patients = async (query: { page?: number; q?: string }) => {
    const params = new URLSearchParams();
    if (query.page) params.set('page', String(query.page));
    if (query.q) params.set('q', query.q);
    return baseFetch(`/api/patients?${params.toString()}`, {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<Patient>>;
  };

  createPatient = async (payload: {
    fullName: string;
    dateOfBirth?: string;
    phone?: string;
    email?: string;
    medicalCardNumber?: string;
    gender?: string;
    notes?: string;
  }) => {
    return baseFetch('/api/patients', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  appointments = async (query: { page?: number; q?: string; from?: string; to?: string }) => {
    const params = new URLSearchParams();
    if (query.page) params.set('page', String(query.page));
    if (query.q) params.set('q', query.q);
    if (query.from) params.set('from', query.from);
    if (query.to) params.set('to', query.to);
    return baseFetch(`/api/appointments?${params.toString()}`, {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<Appointment>>;
  };

  createAppointment = async (payload: {
    patientId: number;
    providerId?: number;
    serviceId?: number;
    startsAt: string;
    endsAt: string;
    reason?: string;
  }) => {
    return baseFetch('/api/appointments', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  treatmentPlans = async (query: { page?: number; q?: string }) => {
    const params = new URLSearchParams();
    if (query.page) params.set('page', String(query.page));
    if (query.q) params.set('q', query.q);
    return baseFetch(`/api/treatment-plans?${params.toString()}`, {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<TreatmentPlan>>;
  };

  createTreatmentPlan = async (payload: {
    patientId: number;
    title: string;
    status: 'draft' | 'active' | 'completed';
    targetFinishAt?: string;
    notes?: string;
  }) => {
    return baseFetch('/api/treatment-plans', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  invoices = async (query: { page?: number; q?: string }) => {
    const params = new URLSearchParams();
    if (query.page) params.set('page', String(query.page));
    if (query.q) params.set('q', query.q);
    return baseFetch(`/api/invoices?${params.toString()}`, {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<Invoice>>;
  };

  createInvoice = async (payload: {
    patientId: number;
    dueDate: string;
    currency: string;
    items: { serviceId: number; description: string; quantity: number; unitPrice: number }[];
  }) => {
    return baseFetch('/api/invoices', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  createPayment = async (invoiceId: number, payload: { amount: number; method: string; referenceNo?: string }) => {
    return baseFetch(`/api/invoices/${invoiceId}/payments`, {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  tasks = async (query: { page?: number; q?: string }) => {
    const params = new URLSearchParams();
    if (query.page) params.set('page', String(query.page));
    if (query.q) params.set('q', query.q);
    return baseFetch(`/api/tasks?${params.toString()}`, {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<Task>>;
  };

  createTask = async (payload: {
    patientId?: number;
    assignedToUserId?: number;
    title: string;
    description?: string;
    dueAt?: string;
    priority: 'low' | 'medium' | 'high';
  }) => {
    return baseFetch('/api/tasks', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  completeTask = async (id: number) => {
    return baseFetch(`/api/tasks/${id}/complete`, {
      method: 'PATCH',
      headers: { ...this.authHeaders() },
    });
  };

  users = async () => {
    return baseFetch('/api/users', {
      headers: { ...this.authHeaders() },
    }) as Promise<{ items: Array<{ id: number; email: string; fullName: string; role: Role; clinicId: number }> }>;
  };

  createUser = async (payload: { email: string; fullName: string; password: string; role: Role; phone?: string }) => {
    return baseFetch('/api/users', {
      method: 'POST',
      headers: { ...this.authHeaders(), 'content-type': 'application/json' },
      body: JSON.stringify(payload),
    });
  };

  jobs = async () => {
    return baseFetch('/api/jobs', {
      headers: { ...this.authHeaders() },
    }) as Promise<Paginated<QueueJob>>;
  };

  runJobs = async () => {
    return baseFetch('/api/jobs/run', {
      method: 'POST',
      headers: { ...this.authHeaders() },
    }) as Promise<{ processed: number }>;
  };
}
