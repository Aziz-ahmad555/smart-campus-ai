-- Optional demo data with fictional people (no real names, no photos).
-- Run after schema.sql on an EMPTY database:
--
--   psql -U postgres -d smart_campus_db -f backend/database/seed.sql
--
-- User accounts are not seeded: create them with
--   python backend/database/create_user.py
-- To sign in as the demo teacher, create a teacher account and link it to
-- staff record 1 ("Demo Teacher One"); create_user.py asks for the link.

INSERT INTO classes (name, grade_level, section) VALUES
    ('Grade 9 - A',  '9',  'A'),
    ('Grade 10 - B', '10', 'B');

INSERT INTO students (name, roll_number, photo_folder, class_id) VALUES
    ('Demo Student Alpha',   'DEMO-001', 'DemoStudentAlpha',   1),
    ('Demo Student Bravo',   'DEMO-002', 'DemoStudentBravo',   1),
    ('Demo Student Charlie', 'DEMO-003', 'DemoStudentCharlie', 2),
    ('Demo Student Delta',   'DEMO-004', 'DemoStudentDelta',   NULL);

INSERT INTO staff (name, role, department, photo_folder, class_id) VALUES
    ('Demo Teacher One',  'Teacher',     'Computer Science', 'DemoTeacherOne',  1),
    ('Demo Guard One',    'Security',    'Main Gate',        'DemoGuardOne',    NULL),
    ('Demo Office Staff', 'Admin Staff', 'Registrar',        'DemoOfficeStaff', NULL);

INSERT INTO visitors (name, cnic_or_id, reason, host_name, allowed_minutes, check_in_time) VALUES
    ('Demo Visitor One', NULL, 'Parent meeting', 'Demo Teacher One', 45, CURRENT_TIMESTAMP - INTERVAL '10 minutes'),
    ('Demo Visitor Two', NULL, 'Delivery',       'Registrar',        15, CURRENT_TIMESTAMP - INTERVAL '30 minutes');
