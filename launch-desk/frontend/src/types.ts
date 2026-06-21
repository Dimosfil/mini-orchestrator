export type Role =
  | 'owner'
  | 'admin'
  | 'dentist'
  | 'assistant'
  | 'receptionist'
  | 'billing'
  | 'viewer';

export type User = {
  id: number;
  email: string;
  fullName: string;
  role: Role;
  clinicId: number;
  lastLoginAt: string | null;
};

export type LoginRequest = { email: string; password: string };

export type AuditEntry = {
  id: number;
  action: string;
  created_at: string;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export type Patient = {
  id: number;
  full_name: string;
  phone: string | null;
  email: string | null;
  date_of_birth: string | null;
  deleted_at: string | null;
};

export type Appointment = {
  id: number;
  patient_id: number;
  provider_id: number | null;
  starts_at: string;
  ends_at: string;
  status: string;
  reason: string | null;
  patientName?: string;
};

export type TreatmentPlan = {
  id: number;
  title: string;
  status: string;
  target_finish_at: string | null;
  total_cost: number;
  patientName?: string;
};

export type Invoice = {
  id: number;
  status: string;
  total: number;
  currency: string;
  due_date: string;
  patientName: string;
};

export type Task = {
  id: number;
  title: string;
  description: string | null;
  due_at: string | null;
  status: string;
  priority: string;
};

export type QueueJob = {
  id: number;
  type: string;
  status: string;
  attempts: number;
  max_attempts: number;
  next_attempt_at: string;
  last_error: string | null;
};
