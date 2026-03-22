"""
UI extensions for the Kiro Users Report dashboard.
Sidebar navigation and additional dashboard sections.
Data cleaning (userid normalization) is handled by the Athena View layer.
"""

import streamlit as st
import streamlit.components.v1 as components
import plotly.express as px


import re

_nav_items = []
_nav_placeholder = None


def _slugify(text):
    """Generate anchor slug from header text, stripping emoji."""
    clean = re.sub(r'[^\w\s-]', '', text).strip().lower()
    return re.sub(r'[\s_]+', '-', clean)


def section_header(text):
    """st.header wrapper that auto-registers to sidebar navigation."""
    anchor_id = _slugify(text)
    _nav_items.append((text, anchor_id))
    st.header(text, anchor=anchor_id)


def render_sidebar_nav():
    global _nav_placeholder, _nav_items
    _nav_items = []  # reset on each rerun
    st.sidebar.markdown("## 🧭 Quick Navigation")
    _nav_placeholder = st.sidebar.empty()


def flush_sidebar_nav():
    if _nav_placeholder and _nav_items:
        _nav_placeholder.markdown(
            "\n".join(f"- [{text}](#{aid})" for text, aid in _nav_items)
        )


def render_credits_balance(table_name, fetch_data, safe_float,
                           get_usernames_batch, apply_chart_theme, current_theme):
    section_header("💳 Credits Balance by User (Current Month)")

    query = f"""
    SELECT userid,
        MAX(client_type) as client_type,
        MAX(subscription_tier) as subscription_tier,
        SUM(TRY_CAST(credits_used AS DOUBLE)) as total_used
    FROM {table_name}
    WHERE date >= date_format(current_date, '%Y-%m-01')
    GROUP BY userid
    """
    bal = fetch_data(query)
    bal['total_used'] = bal['total_used'].apply(safe_float)

    tier_limits = {'PRO': 1000, 'PROPLUS': 2000, 'POWER': 10000}
    bal['credit_limit'] = bal['subscription_tier'].apply(
        lambda t: tier_limits.get(str(t).upper().replace('_', '').replace('-', '').strip(), 1000))

    umap = get_usernames_batch(bal['userid'].tolist())
    bal['username'] = bal['userid'].map(umap)
    bal['remaining'] = bal['credit_limit'] - bal['total_used']
    bal['usage_pct'] = (bal['total_used'] / bal['credit_limit'] * 100).round(1)
    bal = bal.sort_values('total_used', ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(bal.head(20), x='total_used', y='username', orientation='h',
                     title='Top 20 Users by Credits Used',
                     color='usage_pct', color_continuous_scale='RdYlGn_r',
                     labels={'total_used': 'Credits Used', 'username': 'User', 'usage_pct': 'Usage %'})
        fig.update_traces(marker_line_width=0)
        fig.update_yaxes(autorange='reversed')
        apply_chart_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("📋 Credits Balance Table")
        disp = bal[['username', 'client_type', 'subscription_tier',
                     'credit_limit', 'total_used', 'remaining', 'usage_pct']].copy()
        disp.columns = ['User', 'Client_Type', 'Tier', 'Limit', 'Used', 'Remaining', 'Usage %']
        disp = disp.sort_values('Used', ascending=False)
        disp.insert(0, 'Rank', range(1, len(disp) + 1))

        html = disp.to_html(index=False, table_id='balanceTable', border=0)
        bg, sbg = current_theme['bg'], current_theme['secondary_bg']
        tc, bc = current_theme['text'], current_theme['border']

        components.html(f"""
        <style>
        body{{background:{bg};color:{tc};font-family:Inter,system-ui,sans-serif;margin:0}}
        #searchBox{{width:100%;padding:8px 12px;margin-bottom:10px;border:1px solid {bc};border-radius:6px;font-size:14px;background:{sbg};color:{tc};box-sizing:border-box}}
        #balanceTable{{width:100%;border-collapse:collapse;font-size:13px}}
        #balanceTable th{{position:sticky;top:0;background:{sbg};padding:8px 6px;text-align:left;border-bottom:2px solid {bc};color:{tc};cursor:pointer;user-select:none;white-space:nowrap}}
        #balanceTable th:hover{{background:{bc}}}
        #balanceTable th .sa{{margin-left:4px;font-size:10px;opacity:.4}}
        #balanceTable td{{padding:6px;border-bottom:1px solid {bc};color:{tc}}}
        #balanceTable tr:hover{{background:{sbg}}}
        </style>
        <input type="text" id="searchBox" placeholder="🔍 Search...">
        <div style="overflow-y:auto;max-height:520px">{html}</div>
        <script>
        document.getElementById('searchBox').addEventListener('input',function(){{
          var v=this.value.toLowerCase();
          document.querySelectorAll('#balanceTable tbody tr').forEach(function(r){{
            r.style.display=r.textContent.toLowerCase().includes(v)?'':'none'}})
        }});
        (function(){{
          var t=document.getElementById('balanceTable'),hs=t.querySelectorAll('th'),ss={{}};
          hs.forEach(function(h,i){{
            var a=document.createElement('span');a.className='sa';a.textContent='▲▼';h.appendChild(a);
            h.addEventListener('click',function(){{
              var asc=ss[i]!=='asc';
              Object.keys(ss).forEach(function(k){{hs[k].querySelector('.sa').textContent='▲▼'}});
              ss={{}};ss[i]=asc?'asc':'desc';h.querySelector('.sa').textContent=asc?'▲':'▼';
              var tb=t.querySelector('tbody'),rows=Array.from(tb.querySelectorAll('tr'));
              rows.sort(function(a,b){{
                var av=a.cells[i].textContent.trim(),bv=b.cells[i].textContent.trim();
                var an=parseFloat(av),bn=parseFloat(bv);
                if(!isNaN(an)&&!isNaN(bn))return asc?an-bn:bn-an;
                return asc?av.localeCompare(bv):bv.localeCompare(av)}});
              rows.forEach(function(r){{tb.appendChild(r)}})
            }})
          }})
        }})();
        </script>
        """, height=650)

    st.markdown("---")
