import { FormEvent, useEffect, useState } from 'react';
import type { Appointment, Invoice, Patient, Role, Task, TreatmentPlan, User } from './types';
import { ApiClient } from './api';

type Tab = 'dashboard' | 'patients' | 'appointments' | 'plans' | 'billing' | 'tasks' | 'admin';
type AuthState = { token: string; user: User } | null;

const roleTabs: Record<Tab, Role[]> = {
  dashboard: ['owner', 'admin', 'dentist', 'assistant', 'receptionist', 'billing', 'viewer'],
  patients: ['owner', 'admin', 'dentist', 'assistant', 'receptionist', 'viewer'],
  appointments: ['owner', 'admin', 'dentist', 'assistant', 'receptionist', 'billing'],
  plans: ['owner', 'admin', 'dentist', 'assistant'],
  billing: ['owner', 'admin', 'receptionist', 'billing'],
  tasks: ['owner', 'admin', 'dentist', 'assistant', 'receptionist', 'billing', 'viewer'],
  admin: ['owner', 'admin'],
};

const formatDate = (value: string) => new Date(value).toLocaleString();

export default function App() {
  const [auth, setAuth] = useState<AuthState>(null);
  const [api, setApi] = useState<ApiClient | null>(null);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState('Ready');
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [errorText, setErrorText] = useState('');

  const [dashboard, setDashboard] = useState<{
    summary: { todayAppointments: number; pendingTasks: number; openInvoices: number };
    recentAudit: { id: number; action: string; created_at: string }[];
  } | null>(null);

  const [patients, setPatients] = useState<Patient[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [plans, setPlans] = useState<TreatmentPlan[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [users, setUsers] = useState<{ id: number; email: string; fullName: string; role: Role; clinicId: number }[]>([]);
  const [jobsCount, setJobsCount] = useState(0);
  const [search, setSearch] = useState('');

  const [loginForm, setLoginForm] = useState({ email: '', password: '' });

  const [patientForm, setPatientForm] = useState({
    fullName: '',
    phone: '',
    email: '',
    dateOfBirth: '',
    notes: '',
  });
  const [appointmentForm, setAppointmentForm] = useState({
    patientId: '',
    providerId: '',
    serviceId: '',
    startsAt: '',
    endsAt: '',
    reason: '',
  });
  const [planForm, setPlanForm] = useState({
    patientId: '',
    title: '',
    targetFinishAt: '',
    notes: '',
  });
  const [invoiceForm, setInvoiceForm] = useState({
    patientId: '',
    dueDate: '',
    currency: 'RUB',
    itemDescription: '',
    itemQuantity: '1',
    itemUnitPrice: '',
    itemServiceId: '',
  });
  const [taskForm, setTaskForm] = useState({
    title: '',
    patientId: '',
    description: '',
    dueAt: '',
    priority: 'medium' as 'low' | 'medium' | 'high',
  });
  const [adminUserForm, setAdminUserForm] = useState({
    email: '',
    fullName: '',
    password: '',
    role: 'assistant' as Role,
    phone: '',
  });

  useEffect(() => {
    const raw = localStorage.getItem('dental-crm-token');
    const rawUser = localStorage.getItem('dental-crm-user');
    if (raw && rawUser) {
      try {
        const user = JSON.parse(rawUser) as User;
        setAuth({ token: raw, user });
        setApi(new ApiClient(raw));
      } catch {
        localStorage.removeItem('dental-crm-token');
        localStorage.removeItem('dental-crm-user');
      }
    }
  }, []);

  useEffect(() => {
    if (!api || !auth) {
      return;
    }
    if (activeTab === 'dashboard') {
      void loadDashboard();
    }
    if (activeTab === 'patients') {
      void loadPatients();
    }
    if (activeTab === 'appointments') {
      void loadAppointments();
    }
    if (activeTab === 'plans') {
      void loadTreatmentPlans();
    }
    if (activeTab === 'billing') {
      void loadInvoices();
      void loadTasks();
    }
    if (activeTab === 'tasks') {
      void loadTasks();
    }
    if (activeTab === 'admin' && auth.user.role === 'owner') {
      void loadUsers();
      void loadJobs();
    }
  }, [activeTab, api, auth, search]);

  const setAuthState = (rawToken: string, user: User) => {
    localStorage.setItem('dental-crm-token', rawToken);
    localStorage.setItem('dental-crm-user', JSON.stringify(user));
    setAuth({ token: rawToken, user });
    setApi(new ApiClient(rawToken));
  };

  const clearAuth = () => {
    localStorage.removeItem('dental-crm-token');
    localStorage.removeItem('dental-crm-user');
    setAuth(null);
    setApi(null);
    setStatus('Signed out');
  };

  const onLogin = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const loginClient = api ?? new ApiClient(null);
    setErrorText('');
    setSaving(true);
    setStatus('Signing in...');
    try {
      const response = await loginClient.login(loginForm);
      setAuthState(response.token, response.user);
      setStatus('Signed in');
      setActiveTab('dashboard');
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : 'Sign in failed');
      setStatus('Error');
    } finally {
      setSaving(false);
    }
  };

  const loadDashboard = async () => {
    if (!api) return;
    try {
      const response = await api.dashboard();
      setDashboard(response);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : 'Dashboard load failed');
    }
  };

  const loadPatients = async () => {
    if (!api) return;
    const data = await api.patients({ page: 1, q: search || undefined });
    setPatients(data.items);
  };

  const loadAppointments = async () => {
    if (!api) return;
    const data = await api.appointments({ page: 1, q: search || undefined });
    setAppointments(data.items);
  };

  const loadTreatmentPlans = async () => {
    if (!api) return;
    const data = await api.treatmentPlans({ page: 1, q: search || undefined });
    setPlans(data.items);
  };

  const loadInvoices = async () => {
    if (!api) return;
    const data = await api.invoices({ page: 1, q: search || undefined });
    setInvoices(data.items);
  };

  const loadTasks = async () => {
    if (!api) return;
    const data = await api.tasks({ page: 1, q: search || undefined });
    setTasks(data.items);
  };

  const loadUsers = async () => {
    if (!api) return;
    const data = await api.users();
    setUsers(data.items);
  };

  const loadJobs = async () => {
    if (!api) return;
    const data = await api.jobs();
    setJobsCount(data.total);
  };

  const submitPatient = async () => {
    if (!api) return;
    try {
      await api.createPatient({
        fullName: patientForm.fullName,
        phone: patientForm.phone || undefined,
        email: patientForm.email || undefined,
        dateOfBirth: patientForm.dateOfBirth || undefined,
        notes: patientForm.notes || undefined,
      });
      setPatientForm({ fullName: '', phone: '', email: '', dateOfBirth: '', notes: '' });
      await loadPatients();
      setStatus('Patient added');
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : 'Patient save failed');
    }
  };

  const submitAppointment = async () => {
    if (!api || !appointmentForm.patientId || !appointmentForm.startsAt || !appointmentForm.endsAt) return;
    await api.createAppointment({
      patientId: Number(appointmentForm.patientId),
      providerId: appointmentForm.providerId ? Number(appointmentForm.providerId) : undefined,
      serviceId: appointmentForm.serviceId ? Number(appointmentForm.serviceId) : undefined,
      startsAt: appointmentForm.startsAt,
      endsAt: appointmentForm.endsAt,
      reason: appointmentForm.reason || undefined,
    });
    setAppointmentForm({
      patientId: '',
      providerId: '',
      serviceId: '',
      startsAt: '',
      endsAt: '',
      reason: '',
    });
    await loadAppointments();
  };

  const submitTreatmentPlan = async () => {
    if (!api || !planForm.patientId || !planForm.title) return;
    await api.createTreatmentPlan({
      patientId: Number(planForm.patientId),
      title: planForm.title,
      status: 'draft',
      targetFinishAt: planForm.targetFinishAt || undefined,
      notes: planForm.notes || undefined,
    });
    setPlanForm({ patientId: '', title: '', targetFinishAt: '', notes: '' });
    await loadTreatmentPlans();
  };

  const submitInvoice = async () => {
    if (!api || !invoiceForm.patientId || !invoiceForm.itemDescription || !invoiceForm.itemUnitPrice) return;
    await api.createInvoice({
      patientId: Number(invoiceForm.patientId),
      dueDate: invoiceForm.dueDate || new Date().toISOString().slice(0, 10),
      currency: invoiceForm.currency,
      items: [
        {
          serviceId: Number(invoiceForm.itemServiceId || '1'),
          description: invoiceForm.itemDescription,
          quantity: Math.max(1, Number(invoiceForm.itemQuantity || '1')),
          unitPrice: Number(invoiceForm.itemUnitPrice),
        },
      ],
    });
    setInvoiceForm({
      patientId: '',
      dueDate: '',
      currency: 'RUB',
      itemDescription: '',
      itemQuantity: '1',
      itemUnitPrice: '',
      itemServiceId: '',
    });
    await loadInvoices();
  };

  const submitTask = async () => {
    if (!api || !taskForm.title) return;
    await api.createTask({
      patientId: taskForm.patientId ? Number(taskForm.patientId) : undefined,
      title: taskForm.title,
      description: taskForm.description || undefined,
      dueAt: taskForm.dueAt || undefined,
      priority: taskForm.priority,
    });
    setTaskForm({ title: '', patientId: '', description: '', dueAt: '', priority: 'medium' });
    await loadTasks();
  };

  const submitUser = async () => {
    if (!api) return;
    await api.createUser(adminUserForm);
    setAdminUserForm({ email: '', fullName: '', password: '', role: 'assistant', phone: '' });
    await loadUsers();
  };

  const payInvoice = async (invoiceId: number) => {
    if (!api) return;
    await api.createPayment(invoiceId, { amount: 0, method: 'cash' });
  };

  const quickPay = async (invoiceId: number) => {
    if (!api) return;
    const target = invoices.find((invoice) => invoice.id === invoiceId);
    if (!target) return;
    await api.createPayment(invoiceId, { amount: target.total, method: 'cash', referenceNo: `ref-${Date.now()}` });
    await loadInvoices();
  };

  const completeTask = async (id: number) => {
    if (!api) return;
    await api.completeTask(id);
    await loadTasks();
  };

  const runJobs = async () => {
    if (!api) return;
    const response = await api.runJobs();
    setJobsCount(response.processed);
  };

  const renderDashboard = () => (
    <section className="panel">
      <h2>Dashboard</h2>
      {dashboard ? (
        <>
          <div className="kpis">
            <article>
              <p>Today appointments</p>
              <h3>{dashboard.summary.todayAppointments}</h3>
            </article>
            <article>
              <p>Pending tasks</p>
              <h3>{dashboard.summary.pendingTasks}</h3>
            </article>
            <article>
              <p>Open invoices</p>
              <h3>{dashboard.summary.openInvoices}</h3>
            </article>
          </div>
          <h3>Recent actions</h3>
          <ul>
            {dashboard.recentAudit.map((entry) => (
              <li key={entry.id}>{entry.action} - {entry.created_at}</li>
            ))}
          </ul>
        </>
      ) : <p>Loading...</p>}
    </section>
  );

  const renderPatients = () => (
    <section className="panel">
      <h2>Patients</h2>
      <div className="inline-controls">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search patient" />
      </div>
      <div className="form-grid">
        <input value={patientForm.fullName} onChange={(event) => setPatientForm((prev) => ({ ...prev, fullName: event.target.value }))} placeholder="Full name" />
        <input value={patientForm.phone} onChange={(event) => setPatientForm((prev) => ({ ...prev, phone: event.target.value }))} placeholder="Phone" />
        <input value={patientForm.email} onChange={(event) => setPatientForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="Email" />
        <input value={patientForm.dateOfBirth} onChange={(event) => setPatientForm((prev) => ({ ...prev, dateOfBirth: event.target.value }))} placeholder="Date of birth" />
        <button type="button" onClick={submitPatient} disabled={saving}>{saving ? 'Saving...' : 'Add patient'}</button>
      </div>
      <textarea value={patientForm.notes} onChange={(event) => setPatientForm((prev) => ({ ...prev, notes: event.target.value }))} placeholder="Notes" rows={3} />
      <div className="grid">
        {patients.map((patient) => (
          <article key={patient.id}>
            <h4>{patient.full_name}</h4>
            <p>{patient.phone || '-'} | {patient.email || '-'}</p>
          </article>
        ))}
        {patients.length === 0 ? <p>No patients found</p> : null}
      </div>
    </section>
  );

  const renderAppointments = () => (
    <section className="panel">
      <h2>Appointments</h2>
      <div className="form-grid">
        <input value={appointmentForm.patientId} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, patientId: event.target.value }))} placeholder="Patient ID" />
        <input value={appointmentForm.providerId} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, providerId: event.target.value }))} placeholder="Provider ID (optional)" />
        <input value={appointmentForm.serviceId} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, serviceId: event.target.value }))} placeholder="Service ID" />
        <input value={appointmentForm.startsAt} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, startsAt: event.target.value }))} type="datetime-local" />
        <input value={appointmentForm.endsAt} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, endsAt: event.target.value }))} type="datetime-local" />
        <input value={appointmentForm.reason} onChange={(event) => setAppointmentForm((prev) => ({ ...prev, reason: event.target.value }))} placeholder="Reason" />
        <button type="button" onClick={submitAppointment}>Add appointment</button>
      </div>
      <div className="grid">
        {appointments.map((appointment) => (
          <article key={appointment.id}>
            <h4>{appointment.patientName || `Patient #${appointment.patient_id}`}</h4>
            <p>{formatDate(appointment.starts_at)} → {formatDate(appointment.ends_at)}</p>
            <p>{appointment.status}</p>
          </article>
        ))}
        {appointments.length === 0 ? <p>No appointments</p> : null}
      </div>
    </section>
  );

  const renderPlans = () => (
    <section className="panel">
      <h2>Treatment plans</h2>
      <div className="form-grid">
        <input value={planForm.patientId} onChange={(event) => setPlanForm((prev) => ({ ...prev, patientId: event.target.value }))} placeholder="Patient ID" />
        <input value={planForm.title} onChange={(event) => setPlanForm((prev) => ({ ...prev, title: event.target.value }))} placeholder="Plan title" />
        <input value={planForm.targetFinishAt} onChange={(event) => setPlanForm((prev) => ({ ...prev, targetFinishAt: event.target.value }))} type="date" />
        <input value={planForm.notes} onChange={(event) => setPlanForm((prev) => ({ ...prev, notes: event.target.value }))} placeholder="Plan notes" />
        <button type="button" onClick={submitTreatmentPlan}>Create plan</button>
      </div>
      <div className="grid">
        {plans.map((plan) => (
          <article key={plan.id}>
            <h4>{plan.title}</h4>
            <p>{plan.patientName || `Patient #${plan.id}`}</p>
            <p>{plan.status}</p>
          </article>
        ))}
      </div>
    </section>
  );

  const renderBilling = () => (
    <section className="panel">
      <h2>Billing</h2>
      <div className="form-grid">
        <input value={invoiceForm.patientId} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, patientId: event.target.value }))} placeholder="Patient ID" />
        <input value={invoiceForm.dueDate} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, dueDate: event.target.value }))} placeholder="Due date" />
        <input value={invoiceForm.itemServiceId} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, itemServiceId: event.target.value }))} placeholder="Service ID" />
        <input value={invoiceForm.itemDescription} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, itemDescription: event.target.value }))} placeholder="Item description" />
        <input value={invoiceForm.itemQuantity} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, itemQuantity: event.target.value }))} placeholder="Quantity" />
        <input value={invoiceForm.itemUnitPrice} onChange={(event) => setInvoiceForm((prev) => ({ ...prev, itemUnitPrice: event.target.value }))} placeholder="Unit price" />
        <button type="button" onClick={submitInvoice}>Create invoice</button>
      </div>
      <h3>Invoices</h3>
      <div className="grid">
        {invoices.map((invoice) => (
          <article key={invoice.id}>
            <h4>{invoice.patientName}</h4>
            <p>{invoice.status} | {invoice.total.toFixed(2)} {invoice.currency}</p>
            <p>Due: {invoice.due_date}</p>
            <button type="button" onClick={() => void quickPay(invoice.id)}>Pay full</button>
          </article>
        ))}
      </div>
    </section>
  );

  const renderTasks = () => (
    <section className="panel">
      <h2>Tasks</h2>
      <div className="form-grid">
        <input value={taskForm.patientId} onChange={(event) => setTaskForm((prev) => ({ ...prev, patientId: event.target.value }))} placeholder="Patient ID" />
        <input value={taskForm.title} onChange={(event) => setTaskForm((prev) => ({ ...prev, title: event.target.value }))} placeholder="Task title" />
        <input value={taskForm.dueAt} onChange={(event) => setTaskForm((prev) => ({ ...prev, dueAt: event.target.value }))} placeholder="Due ISO date" />
        <select
          value={taskForm.priority}
          onChange={(event) => setTaskForm((prev) => ({ ...prev, priority: event.target.value as 'low' | 'medium' | 'high' }))}
        >
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
        </select>
        <input value={taskForm.description} onChange={(event) => setTaskForm((prev) => ({ ...prev, description: event.target.value }))} placeholder="Description" />
        <button type="button" onClick={submitTask}>Create task</button>
      </div>
      <div className="grid">
        {tasks.map((task) => (
          <article key={task.id}>
            <h4>{task.title}</h4>
            <p>{task.status} - {task.priority}</p>
            <button type="button" onClick={() => void completeTask(task.id)}>Done</button>
          </article>
        ))}
      </div>
    </section>
  );

  const renderAdmin = () => (
    <section className="panel">
      <h2>Administration</h2>
      <div className="form-grid">
        <input value={adminUserForm.email} onChange={(event) => setAdminUserForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="Email" />
        <input value={adminUserForm.fullName} onChange={(event) => setAdminUserForm((prev) => ({ ...prev, fullName: event.target.value }))} placeholder="Full name" />
        <input value={adminUserForm.phone} onChange={(event) => setAdminUserForm((prev) => ({ ...prev, phone: event.target.value }))} placeholder="Phone" />
        <input value={adminUserForm.password} onChange={(event) => setAdminUserForm((prev) => ({ ...prev, password: event.target.value }))} placeholder="Password" type="password" />
        <select
          value={adminUserForm.role}
          onChange={(event) => setAdminUserForm((prev) => ({ ...prev, role: event.target.value as Role }))}
        >
          <option value="owner">owner</option>
          <option value="admin">admin</option>
          <option value="dentist">dentist</option>
          <option value="assistant">assistant</option>
          <option value="receptionist">receptionist</option>
          <option value="billing">billing</option>
          <option value="viewer">viewer</option>
        </select>
        <button type="button" onClick={submitUser}>Create user</button>
      </div>
      <h3>Users</h3>
      <div className="grid">
        {users.map((user) => (
          <article key={user.id}>
            <h4>{user.fullName}</h4>
            <p>{user.email}</p>
            <p>{user.role}</p>
          </article>
        ))}
      </div>
      <h3>Background jobs</h3>
      <p>Pending/total rows: {jobsCount}</p>
      <button type="button" onClick={runJobs}>Run worker now</button>
    </section>
  );

  if (!auth || !api) {
    return (
      <main className="auth-shell">
          <section className="panel">
            <h1>Dental CRM</h1>
          <form onSubmit={onLogin} className="form-grid">
            <input
              required
              placeholder="Email"
              value={loginForm.email}
              onChange={(event) => setLoginForm((prev) => ({ ...prev, email: event.target.value }))}
            />
            <input
              required
              placeholder="Password"
              type="password"
              value={loginForm.password}
              onChange={(event) => setLoginForm((prev) => ({ ...prev, password: event.target.value }))}
            />
            <button type="submit" disabled={saving}>{saving ? 'Signing in...' : 'Sign in'}</button>
          </form>
          {errorText ? <p className="error">{errorText}</p> : null}
          <p className="muted">V1 CRM for Dental Clinic. RBAC, auth, schedules, billing, tasks, jobs.</p>
        </section>
      </main>
    );
  }

  const canVisit = roleTabs[activeTab].includes(auth.user.role);

  return (
    <div className="page">
      <header className="topbar">
        <div>
          <p className="eyebrow">Dental CRM</p>
          <h1>Dental Operations Console</h1>
        </div>
        <div className="status">
          <p>{auth.user.fullName}</p>
          <p>{auth.user.role}</p>
          <button type="button" onClick={clearAuth}>Logout</button>
        </div>
      </header>
      <nav className="tabs">
        {Object.keys(roleTabs).map((tab) => {
          const key = tab as Tab;
          const enabled = roleTabs[key].includes(auth.user.role);
          return (
            <button
              key={tab}
              type="button"
              disabled={!enabled}
              className={key === activeTab ? 'active' : ''}
              onClick={() => {
                if (enabled) {
                  setActiveTab(key);
                  setSearch('');
                }
              }}
            >
              {key}
            </button>
          );
        })}
      </nav>
      <section className="panel">{canVisit ? null : <p className="error">Access denied</p>}</section>
      <main>
        {activeTab === 'dashboard' && renderDashboard()}
        {activeTab === 'patients' && renderPatients()}
        {activeTab === 'appointments' && renderAppointments()}
        {activeTab === 'plans' && renderPlans()}
        {activeTab === 'billing' && renderBilling()}
        {activeTab === 'tasks' && renderTasks()}
        {activeTab === 'admin' && renderAdmin()}
      </main>
      <section className="status-line">
        <span>{status}</span>
        {errorText ? <span className="error">{errorText}</span> : null}
      </section>
    </div>
  );
}
