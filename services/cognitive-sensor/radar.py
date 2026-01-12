import sqlite3

con = sqlite3.connect("results.db")
cur = con.cursor()

# Common filler words to ignore
STOP = set("""
like can just what not but how their have when because about could might his her him them that this there then than more some very will would should may also even now get got make made going way back down out over only other into through where which been being all any both each few many most much such same too well say said did had has does done
""".split())

def clean(rows):
    return [(t, w) for t, w in rows if t not in STOP][:5]

# Rising = last 90 days of data vs previous 90 days
q_rising = f"""
SELECT t.topic, SUM(t.weight) AS total
FROM topics t
JOIN convo_time c ON t.convo_id = c.convo_id
WHERE c.date >= (SELECT date(MAX(date), '-90 day') FROM convo_time)
GROUP BY t.topic
ORDER BY total DESC
LIMIT 50;
"""

q_prev = f"""
SELECT t.topic, SUM(t.weight) AS total
FROM topics t
JOIN convo_time c ON t.convo_id = c.convo_id
WHERE c.date < (SELECT date(MAX(date), '-90 day') FROM convo_time)
  AND c.date >= (SELECT date(MAX(date), '-180 day') FROM convo_time)
GROUP BY t.topic
ORDER BY total DESC
LIMIT 50;
"""

recent = dict(cur.execute(q_rising).fetchall())
previous = dict(cur.execute(q_prev).fetchall())

rising = sorted([(t, recent[t] - previous.get(t,0)) for t in recent], key=lambda x: x[1], reverse=True)
fading = sorted([(t, previous[t] - recent.get(t,0)) for t in previous], key=lambda x: x[1], reverse=True)

# Stable = lifetime anchors
q_stable = """
SELECT topic, SUM(weight) AS total
FROM topics
GROUP BY topic
ORDER BY total DESC
LIMIT 50;
"""
stable = clean(cur.execute(q_stable).fetchall())

print("\n=== YOUR PERSONAL RADAR ===\n")

print("WHAT IS RISING:")
for t,w in clean(rising):
    print(f"  {t:<15} +{w}")

print("\nWHAT IS FADING:")
for t,w in clean(fading):
    print(f"  {t:<15} -{w}")

print("\nWHAT STAYS CONSTANT:")
for t,w in stable:
    print(f"  {t:<15}  {w}")

con.close()
