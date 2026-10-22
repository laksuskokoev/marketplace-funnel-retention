-- PostgreSQL. Import data/events_synthetic.csv into events(user_id text,
-- event_time timestamp, event_name text, channel text, device text, revenue numeric).
-- The Python version additionally enforces ordered steps in the first 7 days.

-- 1. Registrations, buyers and revenue by acquisition channel
WITH registered AS (
  SELECT user_id, MIN(event_time) AS signup_time, MIN(channel) AS channel
  FROM events WHERE event_name='signup' GROUP BY user_id
), buyer_7d AS (
  SELECT DISTINCT e.user_id
  FROM events e JOIN registered r USING(user_id)
  WHERE e.event_name='purchase' AND e.event_time >= r.signup_time
    AND e.event_time < r.signup_time + INTERVAL '7 days'
)
SELECT r.channel, COUNT(*) AS registered_users,
       COUNT(b.user_id) AS buyers_7d,
       ROUND(COUNT(b.user_id)::numeric / NULLIF(COUNT(*),0),4) AS purchase_cr_7d
FROM registered r LEFT JOIN buyer_7d b USING(user_id)
GROUP BY r.channel ORDER BY registered_users DESC;

-- 2. Funnel: stage reach (unique users, within 7 days of signup)
WITH registered AS (
  SELECT user_id, MIN(event_time) AS signup_time FROM events
  WHERE event_name='signup' GROUP BY user_id
), reached AS (
  SELECT r.user_id, e.event_name
  FROM registered r JOIN events e USING(user_id)
  WHERE e.event_time >= r.signup_time
    AND e.event_time < r.signup_time + INTERVAL '7 days'
    AND e.event_name IN ('signup','view_item','add_to_cart','begin_checkout','purchase')
  GROUP BY r.user_id,e.event_name
)
SELECT event_name, COUNT(*) AS users FROM reached GROUP BY event_name;
-- Caveat: this SQL counts presence, NOT strictly ordered transitions.
-- Compare to Python's ordered-funnel definition before drawing conclusions.

-- 3. Day-7 retention (only users with a fully observable 7th day)
WITH users AS (
  SELECT user_id, MIN(event_time) AS signup_time FROM events
  WHERE event_name='signup' GROUP BY user_id
), eligible AS (
 SELECT * FROM users WHERE signup_time + INTERVAL '8 days' <= TIMESTAMP '2026-10-21 23:59:59'
)
SELECT COUNT(*) AS eligible_users,
 COUNT(*) FILTER (WHERE EXISTS(
 SELECT 1 FROM events e WHERE e.user_id=eligible.user_id AND e.event_name <> 'signup'
   AND e.event_time >= eligible.signup_time + INTERVAL '7 days'
   AND e.event_time < eligible.signup_time + INTERVAL '8 days')) AS retained_d7
FROM eligible;
