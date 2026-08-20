from pathlib import Path
from itertools import combinations
from collections import defaultdict
from bs4 import BeautifulSoup
import re, json, html

ROOT = Path('/home/ubuntu/statecompare-audit/repo')
TARGET = 1000
BASE_URL = 'https://statetaxcompare.github.io'
REFERENCE = ROOT / 'california-vs-texas.html'

raw_index = (ROOT / 'index.html').read_text(encoding='utf-8', errors='ignore')
state_data = {}
for m in re.finditer(r'([A-Z]{2}):\{f:"([^"]+)",tax:([0-9.]+),rent:([0-9]+),groc:([0-9]+),gas:([0-9.]+)\}', raw_index):
    code, name, tax, rent, groc, gas = m.groups()
    state_data[name] = {
        'code': code,
        'name': name,
        'tax': float(tax),
        'rent': int(rent),
        'groc': int(groc),
        'gas': float(gas),
    }
if len(state_data) != 50:
    raise RuntimeError(f'Expected 50 states, found {len(state_data)}')

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def monthly_cost(state):
    return state['rent'] + round(600 * state['groc'] / 100) + round(state['gas'] * 40) + 300

def money(value):
    return f'${value:,.0f}'

def rate(value):
    return 'No state income tax' if value == 0 else f'{value:g}%'

# Preserve existing URLs where possible, but normalize identity by unordered pair.
existing_by_pair = defaultdict(list)
for p in ROOT.glob('*-vs-*.html'):
    a, b = p.stem.split('-vs-', 1)
    if a in {slug(n) for n in state_data} and b in {slug(n) for n in state_data}:
        existing_by_pair['-vs-'.join(sorted((a, b)))].append(p.name)

all_pairs = []
for left, right in combinations(sorted(state_data), 2):
    key = '-vs-'.join(sorted((slug(left), slug(right))))
    all_pairs.append((key, left, right))

existing_unique = [x for x in all_pairs if x[0] in existing_by_pair]
selected = existing_unique[:]
for pair in all_pairs:
    if len(selected) >= TARGET:
        break
    if pair[0] not in {x[0] for x in selected}:
        selected.append(pair)
if len(selected) != TARGET:
    raise RuntimeError(f'Could not select {TARGET} unique pairs; selected {len(selected)}')

# Reuse the exact comparison-page stylesheet so the visual language remains unchanged.
ref_soup = BeautifulSoup(REFERENCE.read_text(encoding='utf-8', errors='ignore'), 'html.parser')
style = ref_soup.find('style')
if not style:
    raise RuntimeError('Reference comparison page has no inline style')
STYLE = style.get_text()

source_links = (
    '<a href="https://taxfoundation.org" target="_blank" rel="noopener">Tax Foundation</a> & '
    '<a href="https://www.irs.gov" target="_blank" rel="noopener">IRS.gov</a>; '
    '<a href="https://www.bls.gov" target="_blank" rel="noopener">BLS</a>; '
    '<a href="https://www.census.gov" target="_blank" rel="noopener">U.S. Census Bureau</a>; '
    '<a href="https://www.eia.gov" target="_blank" rel="noopener">EIA</a>'
)

def render_page(left_name, right_name, filename):
    left, right = state_data[left_name], state_data[right_name]
    left_cost, right_cost = monthly_cost(left), monthly_cost(right)
    cheaper, expensive = (left, right) if left_cost <= right_cost else (right, left)
    savings = abs(left_cost - right_cost) * 12
    title = f'{left_name} vs {right_name} Taxes & Cost of Living 2026'
    description = f'Compare {left_name} vs {right_name} taxes, cost of living, rent, gas and monthly expenses in 2026.'
    def card(s, cls):
        tax_class = 'good' if s['tax'] == 0 else 'bad'
        tax_value = '✓ None' if s['tax'] == 0 else rate(s['tax'])
        cost_class = 'good' if monthly_cost(s) == min(left_cost, right_cost) else 'bad'
        return f'''<div class="card {cls}"><h2>{html.escape(s['name'])}</h2>
<div class="row"><span class="label">State Income Tax</span><span class="{tax_class}">{tax_value}</span></div>
<div class="row"><span class="label">Median Rent</span><span class="{cost_class}">{money(s['rent'])}/mo</span></div>
<div class="row"><span class="label">Gas per Gallon</span><span class="{cost_class}">${s['gas']:.2f}</span></div>
<div class="row"><span class="label">Groceries Index</span><span class="{cost_class}">{s['groc']}/100</span></div>
<div class="row"><span class="label">Est. Monthly Cost</span><span class="{cost_class}">{money(monthly_cost(s))}</span></div></div>'''
    a = html.escape(left_name)
    b = html.escape(right_name)
    content = f'''<div class="content"><h3>Comparing {a} and {b}</h3>
<p>This page compares the state income-tax rate, median rent, groceries index, gasoline price and estimated monthly cost recorded in the StateTaxCompare dataset for 2026. The estimate is a baseline for one adult and is not a personalized tax calculation.</p>
<h3>Monthly cost difference</h3>
<p>Using the same formula as the main comparison tool, {html.escape(cheaper['name'])} has the lower estimated monthly cost in this pair. The displayed annual difference is the monthly difference multiplied by twelve.</p>
<h3>What to verify before moving</h3>
<p>Actual results depend on income, household size, city, housing choice, insurance, commuting and local taxes. Review current official rates and local costs before making a relocation decision.</p></div>'''
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(description)}"><link rel="canonical" href="{BASE_URL}/{filename}"><script type="application/ld+json">{{"@context":"https://schema.org","@type":"WebPage","name":{json.dumps(title)},"description":{json.dumps(description)},"url":{json.dumps(BASE_URL+'/'+filename)},"mainEntity":{{"@type":"Table","about":"State Tax Comparison","description":{json.dumps(left_name+' vs '+right_name)}}}}}</script><style>{STYLE}</style></head><body><header><h1>🇺🇸 {a} vs {b}</h1><p>Taxes & Cost of Living Comparison 2026</p></header><div class="container">{card(left,'ca')}{card(right,'tx')}<div class="save"><h3>Annual Savings in {html.escape(cheaper['name'])}</h3><div class="amount">{money(savings)}</div><small>compared to living in {html.escape(expensive['name'])}</small></div>{content}<div class="cta"><p>Compare any two states with our free tool</p><a href="{BASE_URL}">Use our Full Comparison Tool Now</a></div><div class="sources"><h4>Data Sources</h4><p>{source_links}</p></div></div><footer>© 2026 US State Tax Compare | <a href="{BASE_URL}">StateTaxCompare.github.io</a> | <a href="{BASE_URL}/methodology.html">Methodology</a></footer></body></html>'''

manifest=[]
selected_keys={x[0] for x in selected}
for key, left_name, right_name in selected:
    filename = existing_by_pair[key][0] if existing_by_pair.get(key) else f'{slug(left_name)}-vs-{slug(right_name)}.html'
    # Ensure no old reciprocal URL is selected as the canonical page for the duplicate pair.
    if key == 'florida-vs-new-york' and 'florida-vs-new-york.html' in existing_by_pair[key]:
        filename = 'florida-vs-new-york.html'
    (ROOT / filename).write_text(render_page(left_name, right_name, filename), encoding='utf-8')
    manifest.append({'file': filename, 'left': left_name, 'right': right_name, 'key': key, 'monthly_left': monthly_cost(state_data[left_name]), 'monthly_right': monthly_cost(state_data[right_name]), 'annual_savings': abs(monthly_cost(state_data[left_name])-monthly_cost(state_data[right_name]))*12})

# Preserve the old reciprocal URL without serving duplicate comparison content.
redirect = '''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="robots" content="noindex,follow"><link rel="canonical" href="https://statetaxcompare.github.io/florida-vs-new-york.html"><meta http-equiv="refresh" content="0; url=florida-vs-new-york.html"><title>Redirecting to Florida vs New York</title></head><body><p>Redirecting to <a href="florida-vs-new-york.html">Florida vs New York</a>.</p></body></html>'''
(ROOT/'new-york-vs-florida.html').write_text(redirect, encoding='utf-8')

# Add a machine-readable data file for maintenance and future regeneration.
data_dir=ROOT/'data'
data_dir.mkdir(exist_ok=True)
(data_dir/'us-states.json').write_text(json.dumps(list(state_data.values()), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
(ROOT/'comparison-manifest.json').write_text(json.dumps({'target_unique_us_comparisons':TARGET,'comparisons':manifest}, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

# Generate a complete sitemap from actual generated pages plus special pages.
special = ['index.html','methodology.html','aca-subsidy-cliff-calculator.html','canada.html','ontario-vs-alberta.html']
urls = [BASE_URL+'/' if x=='index.html' else BASE_URL+'/'+x for x in special]
urls += [BASE_URL+'/'+x['file'] for x in manifest]
xml = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u in urls:
    priority = '1.0' if u == BASE_URL+'/' else ('0.7' if 'methodology' in u else '0.9')
    xml.append(f'  <url><loc>{u}</loc><priority>{priority}</priority></url>')
xml.append('</urlset>')
(ROOT/'sitemap.xml').write_text('\n'.join(xml)+'\n', encoding='utf-8')

# Update README with reproducibility information.
(ROOT/'README.md').write_text('''# statetaxcompare.github.io\n\nStatic StateTaxCompare site. The repository contains the main interactive tool, methodology, ACA calculator, Canada province comparator, and generated US state comparison pages.\n\nThe generated comparison set contains 1,000 unique unordered pairs from the 50 US states. Canonical pair identity is normalized alphabetically so reciprocal URLs cannot create duplicate comparison content.\n''', encoding='utf-8')

# Copy the generator into the repository as a maintenance tool.
(ROOT/'tools').mkdir(exist_ok=True)
Path('/home/ubuntu/statecompare-audit/generate_comparisons.py').replace(ROOT/'tools'/'generate_comparisons.py')
print(json.dumps({'states':len(state_data),'unique_comparisons':len(manifest),'total_html':len(list(ROOT.glob('*.html'))),'sitemap_urls':len(urls),'removed_duplicate_to_redirect':'new-york-vs-florida.html'},ensure_ascii=False))
