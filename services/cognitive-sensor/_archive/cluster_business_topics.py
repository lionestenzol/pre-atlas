import json
import sqlite3
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.resolve()
conn = sqlite3.connect(BASE / "results.db")
cur = conn.cursor()

# Define search results from all searches run
search_data = {
    'Business/Startup': [
        (513, 'Starting a Business Roadmap', '2025-02-08', 60.7),
        (654, 'Readiness for Startup', '2025-01-25', 49.2),
        (1139, 'Business Conglomerate Blueprint', '2024-11-16', 46.8),
        (1142, 'Business Ecosystem Integration', '2024-11-15', 43.4),
        (520, 'Launch SaaS Business Guide', '2025-02-08', 42.0),
        (664, 'Million Dollar Plan', '2025-01-24', 40.5),
        (799, 'AI Business Solutions', '2025-01-02', 38.3),
        (939, 'Business Plan Creation Guide', '2024-12-03', 35.0),
        (185, "CEO's Struggles and Sacrifices", '2025-03-03', 34.6),
        (1140, 'Business Model Breakdown', '2024-11-16', 33.3),
    ],
    'Money/Finance/Wealth': [
        (282, 'Money Mindset Analysis', '2025-02-27', 40.6),
        (670, 'Making $1M Fast', '2025-01-24', 39.0),
        (588, 'Exponential Functions Quiz Help', '2025-01-29', 33.2),
        (225, 'AI Hybrid Economy Concept', '2025-03-01', 29.6),
        (718, 'Wealth and Happiness Paradox', '2025-01-15', 29.5),
        (418, 'Tangible Bitcoin Value', '2025-02-18', 29.4),
        (1144, 'Debt Freedom in 4 Weeks', '2024-11-16', 28.8),
        (1394, 'Creative Ways to Earn', '2024-08-21', 28.6),
    ],
    'Income/Earnings': [
        (379, 'Revenue Function Equation', '2025-02-21', 33.5),
        (885, 'Deferred Compensation Overview', '2024-12-10', 29.9),
        (972, 'Dynamic Pay with Crypto', '2024-11-29', 29.0),
        (981, '15 Days Work Earnings', '2024-11-29', 28.7),
        (154, 'Payroll Processing Schedule Analysis', '2025-03-05', 26.3),
        (737, '300k Income Subscriptions', '2025-01-11', 22.1),
        (84, 'Make $500 by Tuesday', '2025-03-09', 21.3),
        (1129, 'Earnings Calculation', '2024-11-20', 20.0),
    ],
    'Job/Career/Work': [
        (873, 'Simplified Definitions for Kids', '2024-12-11', 47.1),
        (1171, 'LinkedIn Career Explorer Tool', '2024-11-09', 46.2),
        (839, 'Gaming and Sales Skills', '2024-12-17', 34.8),
        (1304, 'Career Interests and Opportunities', '2024-10-14', 33.9),
        (704, 'Farming Gardening and Business', '2025-01-19', 32.8),
        (1170, 'Career Progression Analysis', '2024-11-09', 26.7),
        (1328, 'Training Development Employee Engagement', '2024-10-11', 25.4),
    ],
    'Poverty/Debt/Struggle': [
        (1115, 'From Stress to Confidence', '2024-11-21', 34.1),
        (1144, 'Debt Freedom in 4 Weeks', '2024-11-16', 33.5),
        (718, 'Wealth and Happiness Paradox', '2025-01-15', 31.5),
        (1395, "Liam's MOHELA Date Inquiry", '2024-08-21', 28.9),
        (1296, 'Life Organization and Planning', '2024-10-15', 27.5),
        (733, 'Resilience and Strategic Growth', '2025-01-11', 27.3),
        (92, 'Money as Closure', '2025-03-08', 25.1),
        (1392, 'Loan Maxing and Adjustment', '2024-08-22', 25.4),
    ],
    'Side Hustle/Freelance': [
        (84, 'Make $500 by Tuesday', '2025-03-09', 55.2),
        (150, 'Make $200 a Day', '2025-03-05', 44.8),
        (1144, 'Debt Freedom in 4 Weeks', '2024-11-16', 42.9),
        (1394, 'Creative Ways to Earn', '2024-08-21', 40.9),
        (82, 'Phone Farming Overview', '2025-03-09', 33.6),
        (710, 'SaaS Automation with Make', '2025-01-11', 32.6),
        (37, 'How to Get $10', '2025-03-11', 29.9),
    ],
    'Sales/Marketing': [
        (857, 'Sales Approach Review', '2024-12-13', 55.3),
        (914, 'Unit 2 3 Crash Course', '2024-12-06', 53.0),
        (879, 'PA results analysis', '2024-12-10', 46.7),
        (902, 'Module 1 Overview', '2024-12-05', 46.0),
        (840, 'Door-to-Door to Real Estate', '2024-12-17', 40.5),
        (47, 'Sales Management Review', '2025-03-10', 39.9),
        (775, 'Law of Averages Guide', '2025-01-05', 39.8),
        (918, 'Social Styles Overview', '2024-12-05', 38.9),
        (321, 'Sales Mastery Through Learning', '2025-02-26', 33.0),
        (49, 'Sales Management Assessment Analysis', '2025-03-09', 31.7),
    ],
    'SaaS/Products/Pricing': [
        (517, 'SaaS Market Growth Trends', '2025-02-08', 54.2),
        (710, 'SaaS Automation with Make', '2025-01-11', 47.6),
        (520, 'Launch SaaS Business Guide', '2025-02-08', 45.2),
        (534, 'Pro Subscription Decision', '2025-02-06', 38.6),
        (102, 'Donation-Based Business Model', '2025-03-07', 36.6),
        (737, '300k Income Subscriptions', '2025-01-11', 35.8),
        (987, 'ChatGPT Integration and AI Investment', '2024-11-28', 34.7),
    ],
    'AI/Automation/Consulting': [
        (708, 'AI Productivity Platform Strategy', '2025-01-18', 69.1),
        (611, 'AI Systems Coordinator Role', '2025-01-29', 67.3),
        (1163, 'Taskade AI Agents Overview', '2024-11-09', 66.5),
        (564, 'AI-assisted coding execution', '2025-02-02', 62.2),
        (628, 'AI Prompt Generation System', '2025-01-27', 61.4),
        (642, 'AI Workflow Optimization Plan', '2025-01-27', 59.5),
        (518, 'AI Ideas Discussion', '2025-02-08', 59.3),
        (1168, 'Task Adequate AI Agents', '2024-11-09', 58.7),
        (1169, 'AI Self-Improvement and Automation', '2024-11-09', 58.3),
        (651, 'AI Agent Analysis Summary', '2025-01-26', 56.2),
        (159, 'Running Multiple AI Projects', '2025-03-04', 56.2),
        (770, 'No-Code AI App Development', '2025-01-06', 55.8),
        (771, 'UI Drafts to AI App', '2025-01-06', 55.8),
        (799, 'AI Business Solutions', '2025-01-02', 55.5),
        (114, 'AI Automation Consulting Blueprint', '2025-03-06', 31.8),
        (119, 'AI Content Systems Consultant', '2025-03-06', 31.8),
    ],
    'Crypto/Trading': [
        (418, 'Tangible Bitcoin Value', '2025-02-18', 47.1),
        (228, 'Crypto Coin Creation Time', '2025-03-01', 41.0),
        (972, 'Dynamic Pay with Crypto', '2024-11-29', 36.9),
        (670, 'Making $1M Fast', '2025-01-24', 33.4),
        (940, 'Scalping Trading Strategy Explained', '2024-12-03', 23.4),
    ],
    'Economy/Systems': [
        (225, 'AI Hybrid Economy Concept', '2025-03-01', 52.5),
        (972, 'Dynamic Pay with Crypto', '2024-11-29', 34.8),
        (1173, 'Bartering Dual Economy System', '2024-11-06', 34.2),
        (519, 'AI Industry Domination Strategy', '2025-02-08', 34.0),
        (241, 'How Monopoly Works', '2025-03-01', 29.6),
        (454, 'US Economy Overview 2025', '2025-02-12', 22.3),
    ],
}

# Deduplicate and track categories
all_convos = {}
for category, items in search_data.items():
    for convo_id, title, date, score in items:
        if convo_id not in all_convos:
            all_convos[convo_id] = {
                'id': convo_id,
                'title': title,
                'date': date,
                'best_score': score,
                'categories': [category]
            }
        else:
            if score > all_convos[convo_id]['best_score']:
                all_convos[convo_id]['best_score'] = score
            if category not in all_convos[convo_id]['categories']:
                all_convos[convo_id]['categories'].append(category)

# Print summary stats
print('=' * 70)
print('DEEP SEARCH RESULTS: BUSINESS, MONEY, WORK & WEALTH')
print('=' * 70)
print()
print(f'Total unique conversations found: {len(all_convos)}')
print(f'Total conversations in database: 1,397')
print(f'Coverage: {len(all_convos)/1397*100:.1f}%')
print()

# Count by category
print('CONVERSATIONS BY CATEGORY:')
print('-' * 40)
for cat in search_data.keys():
    count = len(search_data[cat])
    print(f'  {cat:<30} {count:>3}')
print()

# Strong matches (>50%)
strong = [(k, v) for k, v in all_convos.items() if v['best_score'] >= 50]
strong.sort(key=lambda x: -x[1]['best_score'])
print(f'STRONG MATCHES (>50%): {len(strong)}')
print('-' * 70)
for cid, data in strong:
    cats = ', '.join(data['categories'][:2])
    print(f"  [{data['best_score']:>5.1f}%] {data['title'][:40]:<40} | {cats}")
print()

# Medium matches (30-50%)
medium = [(k, v) for k, v in all_convos.items() if 30 <= v['best_score'] < 50]
medium.sort(key=lambda x: -x[1]['best_score'])
print(f'MEDIUM MATCHES (30-50%): {len(medium)}')
print('-' * 70)
for cid, data in medium:
    cats = ', '.join(data['categories'][:2])
    print(f"  [{data['best_score']:>5.1f}%] {data['title'][:40]:<40} | {cats}")
print()

# Weak but relevant (<30%)
weak = [(k, v) for k, v in all_convos.items() if v['best_score'] < 30]
weak.sort(key=lambda x: -x[1]['best_score'])
print(f'WEAK BUT RELEVANT (<30%): {len(weak)}')
print('-' * 70)
for cid, data in weak:
    cats = ', '.join(data['categories'][:2])
    print(f"  [{data['best_score']:>5.1f}%] {data['title'][:40]:<40} | {cats}")
print()

# Multi-category conversations (appear in 2+ categories)
multi = [(k, v) for k, v in all_convos.items() if len(v['categories']) >= 2]
multi.sort(key=lambda x: -len(x[1]['categories']))
print(f'CROSS-CATEGORY CONVERSATIONS (2+ themes): {len(multi)}')
print('-' * 70)
for cid, data in multi:
    print(f"  {data['title'][:45]:<45}")
    print(f"      Categories: {', '.join(data['categories'])}")
print()

# Cluster summary
print('=' * 70)
print('CLUSTER SUMMARY BY THEME')
print('=' * 70)

clusters = {
    'ENTREPRENEURSHIP & BUSINESS': ['Business/Startup', 'SaaS/Products/Pricing'],
    'MONEY & WEALTH': ['Money/Finance/Wealth', 'Income/Earnings', 'Crypto/Trading'],
    'WORK & CAREER': ['Job/Career/Work', 'Sales/Marketing'],
    'SURVIVAL & STRUGGLE': ['Poverty/Debt/Struggle', 'Side Hustle/Freelance'],
    'AI & AUTOMATION': ['AI/Automation/Consulting'],
    'ECONOMY & SYSTEMS': ['Economy/Systems'],
}

for cluster_name, categories in clusters.items():
    cluster_convos = set()
    for cat in categories:
        for convo_id, title, date, score in search_data.get(cat, []):
            cluster_convos.add(convo_id)
    print(f"\n{cluster_name}")
    print(f"  Categories: {', '.join(categories)}")
    print(f"  Unique conversations: {len(cluster_convos)}")

# Save to JSON
output = {
    'summary': {
        'total_unique_conversations': len(all_convos),
        'total_in_database': 1397,
        'coverage_percent': round(len(all_convos)/1397*100, 1),
        'strong_matches': len(strong),
        'medium_matches': len(medium),
        'weak_matches': len(weak),
        'multi_category': len(multi),
    },
    'clusters': {},
    'conversations': list(all_convos.values()),
}

for cluster_name, categories in clusters.items():
    cluster_convos = []
    seen = set()
    for cat in categories:
        for convo_id, title, date, score in search_data.get(cat, []):
            if convo_id not in seen:
                seen.add(convo_id)
                cluster_convos.append({
                    'id': convo_id,
                    'title': title,
                    'date': date,
                    'score': score,
                    'category': cat
                })
    cluster_convos.sort(key=lambda x: -x['score'])
    output['clusters'][cluster_name] = cluster_convos

with open('business_wealth_clusters.json', 'w') as f:
    json.dump(output, f, indent=2)

print("\n" + "=" * 70)
print("Results saved to business_wealth_clusters.json")
print("=" * 70)

conn.close()
