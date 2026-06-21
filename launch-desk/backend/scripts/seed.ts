import { hashPassword } from '../src/services/security';
import { env, assertConfig } from '../src/config/env';
import { runCommand, getRow, runQuery } from '../src/db';

assertConfig();

const slugify = (value: string) => value.toLowerCase().replace(/[^a-z0-9]+/g, '-');

const existingClinic = getRow<{ id: number }>('SELECT id FROM clinics WHERE name = ?', [env.seedClinicName]);
if (!existingClinic) {
  runCommand(`INSERT INTO clinics (name, address, timezone) VALUES (?, ?, ?)`, [
    env.seedClinicName,
    'Clinic street 1',
    'UTC',
  ]);
}

const clinic = getRow<{ id: number }>('SELECT id FROM clinics WHERE name = ?', [env.seedClinicName]);
if (!clinic) {
  throw new Error('Clinic seed failed');
}

runCommand(
  `INSERT OR IGNORE INTO users (
    clinic_id, email, full_name, password_hash, role, phone
  ) VALUES (?, ?, ?, ?, 'owner', '+79990000000')`,
  [clinic.id, env.seedAdminEmail, env.seedAdminName, hashPassword(env.seedAdminPassword)],
);

const dentistEmail = `dentist.${clinic.id}@${slugify(env.seedClinicName)}.local`;
runCommand(
  `INSERT OR IGNORE INTO users (clinic_id, email, full_name, password_hash, role, phone)
   VALUES (?, ?, 'Demo Dentist', ?, 'dentist', '+79990000001')`,
  [clinic.id, dentistEmail, hashPassword('dentist-demo')],
);

const services = [
  ['EXAM', 'General exam', 60, 2200],
  ['SCALING', 'Professional cleaning', 45, 1800],
  ['FILLING', 'Restorative filling', 50, 3500],
  ['ORTHO', 'Orthodontic alignment', 40, 2500],
];

for (const service of services) {
  const exists = getRow<{ id: number }>(
    `SELECT id FROM services WHERE clinic_id = ? AND code = ?`,
    [clinic.id, service[0]],
  );
  if (!exists) {
    runCommand(
      `INSERT INTO services (clinic_id, code, name, duration_minutes, unit_price)
       VALUES (?, ?, ?, ?, ?)`,
      [clinic.id, service[0], service[1], service[2], service[3]],
    );
  }
}

for (const [idx] of services.entries()) {
  const patientCode = idx + 1;
  const medicalCard = `MC-${String(clinic.id)}-${String(patientCode).padStart(4, '0')}`;
  const existingPatient = getRow<{ id: number }>(
    `SELECT id FROM patients WHERE clinic_id = ? AND medical_card_number = ?`,
    [clinic.id, medicalCard],
  );
  if (!existingPatient) {
    runCommand(
      `INSERT INTO patients (clinic_id, full_name, phone, email, medical_card_number, consent_for_sms, consent_for_call)
       VALUES (?, ?, ?, ?, ?, 1, 1)`,
      [
        clinic.id,
        `Demo Patient ${patientCode}`,
        `+79990000${String(patientCode).padStart(3, '0')}`,
        `patient${patientCode}@example.local`,
        medicalCard,
      ],
    );
  }
}

console.log('Seed data written for clinic', clinic.id);
const counts = [
  runQuery('SELECT COUNT(*) AS c FROM users'),
  runQuery('SELECT COUNT(*) AS c FROM services'),
  runQuery('SELECT COUNT(*) AS c FROM patients'),
];
console.log({
  users: counts[0][0]?.c,
  services: counts[1][0]?.c,
  patients: counts[2][0]?.c,
});
