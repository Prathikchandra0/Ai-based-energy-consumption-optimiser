import os
import time
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_lottie import st_lottie
import json

from utils import find_csv_file, load_data, compute_hourly_price_proxy


def load_lottie_default():
    # Small built-in fallback animation (keeps app lively). If you want, replace with a local/online Lottie JSON.
    # Here we include a minimal animation-like JSON for safe fallback.
    try:
        return json.loads('{"v":"5.5.7","fr":30,"ip":0,"op":60,"w":200,"h":200,"nm":"pulse","ddd":0,"assets":[],"layers":[]}')
    except Exception:
        return None


st.set_page_config(page_title='AI Energy Usage Optimizer', layout='wide')

st.sidebar.title('AI Energy Usage Optimizer')
st.sidebar.markdown('Enter the units you plan to use and get the recommended cheapest hours based on historical data.')

data_path = find_csv_file(os.getcwd())

if not data_path:
    st.warning('No CSV dataset found in the project root. Place a CSV in the project root and re-run. Expected columns: datetime/timestamp and consumption (and optionally cost/bill).')
    st.stop()



df = load_data(data_path)

st.title('AI-Based Energy Consumption Optimizer')

col1, col2 = st.columns([1, 3])

with col1:
    lottie = load_lottie_default()
    if lottie:
        st_lottie(lottie, height=160)
    # Appliance presets and inputs
    st.markdown('#### Appliance preset')
    presets = {
        'Custom': {'units': None, 'duration': None},
        'Washing machine (2h, ~1.5 kWh)': {'units': 1.5, 'duration': 2},
        'Dishwasher (2h, ~1.2 kWh)': {'units': 1.2, 'duration': 2},
        'Water heater (1h, ~3 kWh)': {'units': 3.0, 'duration': 1},
        'EV charging (4h, ~28 kWh)': {'units': 28.0, 'duration': 4},
    }
    preset = st.selectbox('Choose preset (optional)', list(presets.keys()))
    if 'units_input' not in st.session_state:
        st.session_state['units_input'] = 10.0
    if 'duration_input' not in st.session_state:
        st.session_state['duration_input'] = 2
    if preset != 'Custom':
        c = presets[preset]
        if st.button('Use preset values'):
            st.session_state['units_input'] = float(c['units'])
            st.session_state['duration_input'] = int(c['duration'])
    units = st.number_input('Electricity units to schedule (kWh)', min_value=0.1, max_value=10000.0, value=float(st.session_state['units_input']), step=0.1, key='units_input')
    mode = st.radio('Scheduling mode', options=['Continuous block', 'Discrete top-N'], index=0, help='Choose whether to pick a continuous time block or separate cheapest hours')
    if mode == 'Continuous block':
        duration = st.slider('Continuous duration (hours)', min_value=1, max_value=12, value=int(st.session_state['duration_input']), key='duration_input')
        top_n = None
    else:
        top_n = st.slider('How many hours to schedule (top-N cheapest)', min_value=1, max_value=6, value=3)
        duration = None
    excluded_hours = st.multiselect('Exclude these hours (will not be scheduled)', options=list(range(24)), default=[], help='Select hours you cannot use power')
    allowed_window = st.slider('Allowed hours window', 0, 23, (0, 23), help='Only consider hours within this window')
    crosses_midnight = st.checkbox('Window crosses midnight', value=False)
    st.markdown('###### Quick blocked window (e.g., work hours)')
    blk_start, blk_end = st.slider('Blocked window', 0, 23, (18, 22))
    block_cross = st.checkbox('Blocked window crosses midnight', value=False)
    if block_cross:
        blocked_set = {h for h in range(24) if (h >= blk_start or h <= blk_end)}
    else:
        blocked_set = {h for h in range(24) if (blk_start <= h <= blk_end)}
    apply_block = st.checkbox('Apply blocked window to exclusions', value=True)
    if apply_block:
        excluded_hours = sorted(set(excluded_hours) | blocked_set)
    animation_style = st.selectbox('Animation style', ['Incremental bars', 'Units sweep'], index=0)
    hide_excluded_in_charts = st.checkbox('Hide excluded hours in charts', value=False)
    show_notes = st.checkbox('Show help notes', value=False)
    if show_notes:
        st.markdown('---')
        st.markdown('Notes:')
        st.markdown('- This app uses historical hourly patterns from your dataset to recommend cheaper hours.')
        st.markdown('- If your dataset includes cost/bill, the recommendation is directly cost-based. Otherwise it uses consumption as a proxy.')

with col2:
    using_cost = 'cost' in df.columns and df['cost'].notna().any()
    hourly_price = compute_hourly_price_proxy(df)
    # Build a DataFrame for plotting
    hours = pd.DataFrame({'hour': list(range(24)), 'price_per_unit': hourly_price.values})
    hours['expected_cost'] = hours['price_per_unit'] * units
    # Compute allowed set from window selection
    start_w, end_w = allowed_window
    if crosses_midnight:
        allowed_set = set([h for h in range(24) if (h >= start_w or h <= end_w)])
    else:
        allowed_set = set([h for h in range(24) if (start_w <= h <= end_w)])

    # Animated chart styles
    if animation_style == 'Units sweep':
        max_frames = 40
        target_units = int(min(max_frames, max(1, min(500, units))))
        frames = []
        for step in range(1, target_units + 1):
            temp = hours.copy()
            temp['expected_cost'] = temp['price_per_unit'] * step
            temp['step'] = step
            filtered_mask = temp['hour'].isin(excluded_hours) | ~temp['hour'].isin(allowed_set)
            temp['is_excluded'] = filtered_mask.map({True: 'Filtered', False: 'Included'})
            if hide_excluded_in_charts:
                temp = temp[~filtered_mask]
            frames.append(temp)
        anim_df = pd.concat(frames, ignore_index=True)
        fig = px.bar(
            anim_df, x='hour', y='expected_cost', color='is_excluded', animation_frame='step',
            range_y=[0, anim_df['expected_cost'].max()*1.1],
            labels={'expected_cost':('Expected cost' if using_cost else 'Cost index'), 'hour':'Hour of day', 'is_excluded': 'Status'},
            title='Animated — units sweep'
        )
    else:
        frames = []
        for k in range(1, 25):
            temp = hours.copy()
            temp = temp[temp['hour'].isin(list(range(k)))]
            temp['step'] = k
            filtered_mask = temp['hour'].isin(excluded_hours) | ~temp['hour'].isin(allowed_set)
            temp['is_excluded'] = filtered_mask.map({True: 'Filtered', False: 'Included'})
            if hide_excluded_in_charts:
                temp = temp[~filtered_mask]
            frames.append(temp)
        anim_df = pd.concat(frames, ignore_index=True)
        fig = px.bar(
            anim_df, x='hour', y='expected_cost', color='is_excluded', animation_frame='step',
            range_y=[0, anim_df['expected_cost'].max()*1.1],
            labels={'expected_cost':('Expected cost' if using_cost else 'Cost index'), 'hour':'Hour of day', 'is_excluded': 'Status'},
            title='Animated — incremental bars'
        )
    fig.update_traces(marker_line_color='black', marker_line_width=0.3)
    fig.update_layout(legend_title_text='', legend_orientation='h', legend_y=-0.25)
    fig.update_layout(xaxis=dict(tickmode='array', tickvals=list(range(24)), ticktext=[f'{h}:00' for h in range(24)]))
    st.plotly_chart(fig, use_container_width=True)

    # Show static chart for the exact units value
    st.subheader(f'Predicted {"cost" if using_cost else "cost index"} per hour for {units} kWh')
    hours['expected_cost'] = hours['price_per_unit'] * units
    filtered_mask_static = hours['hour'].isin(excluded_hours) | ~hours['hour'].isin(allowed_set)
    hours['is_excluded'] = filtered_mask_static.map({True: 'Filtered', False: 'Included'})
    plot_df = hours if not hide_excluded_in_charts else hours[hours['is_excluded'] == 'Included']
    fig2 = px.bar(
        plot_df, x='hour', y='expected_cost', color='is_excluded',
        labels={'expected_cost':('Expected cost' if using_cost else 'Cost index'), 'hour':'Hour of day', 'is_excluded':'Status'},
        title=f'{"Expected cost" if using_cost else "Cost index"} per hour — {units} kWh'
    )
    fig2.update_layout(xaxis=dict(tickmode='array', tickvals=list(range(24)), ticktext=[f'{h}:00' for h in range(24)]))
    st.plotly_chart(fig2, use_container_width=True)

    # Recommendations
    st.subheader('Top recommended cheapest hours')
    available = hours[hours['hour'].isin(allowed_set) & ~hours['hour'].isin(excluded_hours)].copy()
    if available.empty:
        st.warning('No hours available after applying window and exclusions. Please adjust settings.')
    else:
        if mode == 'Discrete top-N':
            n = min(top_n, len(available))
            rec = available.sort_values('expected_cost').head(n)
            rec_hours_list = [int(h) for h in rec['hour'].tolist()]
            rec_hours_str = ', '.join(f'{h:02d}:00' for h in rec_hours_list)
            st.success(f'For {units} kWh, the best {n} hour(s) within the allowed window are: {rec_hours_str}.')

            rec_display = rec.reset_index(drop=True)
            rec_display['hour_display'] = rec_display['hour'].apply(lambda h: f'{int(h)}:00 - {int(h)}:59')
            rec_display['expected_cost'] = rec_display['expected_cost'].round(3)
            st.table(rec_display[['hour_display', 'expected_cost']].rename(columns={'hour_display':'Hour', 'expected_cost':'Expected Cost'}))

            # Download CSV of recommendations
            csv_bytes = rec_display[['hour_display', 'expected_cost']].to_csv(index=False).encode('utf-8')
            st.download_button('Download recommended hours (CSV)', data=csv_bytes, file_name='recommended_hours.csv', mime='text/csv')

            # Highlight recommended hours on a dedicated chart
            try:
                sel = set(rec_hours_list)
                highlight_df = plot_df.copy()
                highlight_df['selection'] = highlight_df['hour'].astype(int).apply(lambda h: 'Recommended' if h in sel else 'Other')
                fig_sel = px.bar(
                    highlight_df, x='hour', y='expected_cost', color='selection',
                    labels={'expected_cost':'Expected cost', 'hour':'Hour of day', 'selection':'Selection'},
                    title='Recommended hours highlighted'
                )
                fig_sel.update_layout(xaxis=dict(tickmode='array', tickvals=list(range(24)), ticktext=[f'{h}:00' for h in range(24)]))
                st.plotly_chart(fig_sel, use_container_width=True)
            except Exception:
                pass
        else:
            # Continuous block of given duration: distribute units evenly across the block
            allowed_set = set(int(h) for h in available['hour'])
            best_start = None
            best_cost = None
            best_block = None
            for start in range(24):
                block = [(start + i) % 24 for i in range(duration)]
                if all(h in allowed_set for h in block):
                    prices = [float(hours.loc[hours['hour'] == h, 'price_per_unit'].values[0]) for h in block]
                    avg_price = np.mean(prices)
                    # If total units must be used across the block, cost = avg_price * units
                    total_cost = avg_price * float(units)
                    if best_cost is None or total_cost < best_cost:
                        best_cost = total_cost
                        best_start = start
                        best_block = block

            if best_block is None:
                st.warning('No valid continuous block found with the selected duration and exclusions. Try reducing the duration or un-excluding some hours.')
            else:
                block_str = ' → '.join(f'{h:02d}:00' for h in best_block)
                st.success(f'For {units} kWh over a continuous {duration}-hour block, the best window is: {block_str}.')

                # Table per-hour expected cost assuming equal split of units
                per_hour_units = float(units) / duration
                rows = []
                for h in best_block:
                    p = float(hours.loc[hours['hour'] == h, 'price_per_unit'].values[0])
                    rows.append({'Hour': f'{h:02d}:00 - {h:02d}:59', 'Units (split)': round(per_hour_units, 3), 'Expected Cost': round(p * per_hour_units, 3)})
                block_df = pd.DataFrame(rows)
                st.table(block_df)

                # Download CSV for block schedule
                block_csv = block_df.to_csv(index=False).encode('utf-8')
                st.download_button('Download schedule (CSV)', data=block_csv, file_name='continuous_block_schedule.csv', mime='text/csv')

                # Highlight continuous block on a dedicated chart
                try:
                    sel_block = set(int(h) for h in best_block)
                    highlight_df2 = plot_df.copy()
                    highlight_df2['selection'] = highlight_df2['hour'].astype(int).apply(lambda h: 'Selected block' if h in sel_block else 'Other')
                    fig_block = px.bar(
                        highlight_df2, x='hour', y='expected_cost', color='selection',
                        labels={'expected_cost':'Expected cost', 'hour':'Hour of day', 'selection':'Selection'},
                        title='Selected continuous block highlighted'
                    )
                    fig_block.update_layout(xaxis=dict(tickmode='array', tickvals=list(range(24)), ticktext=[f'{h}:00' for h in range(24)]))
                    st.plotly_chart(fig_block, use_container_width=True)
                except Exception:
                    pass

    # Multi-appliance scheduling (optional)
    st.markdown('---')
    st.subheader('Multi-appliance scheduling (optional)')
    multi_mode = st.checkbox('Enable multi-appliance scheduling', value=False, help='Plan multiple appliances at once')
    if multi_mode:
        max_appliances = st.slider('How many appliances to schedule', 1, 5, 2)
        allow_overlap = st.checkbox('Allow appliances to run in parallel (overlap)', value=True)
        # Build appliance inputs
        task_inputs = []
        default_names = ['Washing machine', 'Heater', 'Dishwasher', 'Dryer', 'Custom']
        for i in range(max_appliances):
            with st.expander(f'Appliance {i+1}', expanded=(i < 2)):
                name = st.text_input(f'Name {i+1}', value=default_names[i] if i < len(default_names) else f'Appliance {i+1}')
                units_i = st.number_input(f'Units (kWh) {i+1}', min_value=0.0, value=1.5 if i == 0 else 1.0, step=0.1, key=f'units_i_{i}')
                duration_i = st.number_input(f'Duration (hours) {i+1}', min_value=1, max_value=12, value=2 if i == 0 else 1, step=1, key=f'duration_i_{i}')
                if units_i > 0:
                    task_inputs.append({'name': name.strip() or f'Appliance {i+1}', 'units': float(units_i), 'duration': int(duration_i)})

        def best_block_for_task(task, allowed_set0):
            allowed_set_local = set(int(h) for h in allowed_set0)
            best = None
            for start in range(24):
                block = [(start + k) % 24 for k in range(int(task['duration']))]
                if all(h in allowed_set_local for h in block):
                    prices = [float(hours.loc[hours['hour'] == h, 'price_per_unit'].values[0]) for h in block]
                    avg_price = float(np.mean(prices))
                    total_cost = avg_price * float(task['units'])
                    if best is None or total_cost < best['total_cost']:
                        best = {'start': start, 'block': block, 'avg_price': avg_price, 'total_cost': total_cost}
            return best

        schedule_rows = []
        summary_rows = []
        if task_inputs:
            # Sort by units desc to schedule high-impact tasks first if overlap is not allowed
            tasks_sorted = sorted(task_inputs, key=lambda t: t['units'], reverse=True)
            reserved = set(int(h) for h in excluded_hours) | set([h for h in range(24) if h not in allowed_set])
            for t in tasks_sorted:
                current_allowed = set([h for h in allowed_set if h not in reserved]) if not allow_overlap else set(allowed_set)
                best = best_block_for_task(t, current_allowed)
                if best is None:
                    summary_rows.append({'Appliance': t['name'], 'Schedule': 'Not possible with current constraints', 'Total units': t['units'], 'Estimated total cost': None})
                    continue
                # Reserve if overlap not allowed
                if not allow_overlap:
                    for h in best['block']:
                        reserved.add(int(h))
                per_hour_units = float(t['units']) / int(t['duration'])
                for h in best['block']:
                    p = float(hours.loc[hours['hour'] == h, 'price_per_unit'].values[0])
                    schedule_rows.append({'hour': int(h), 'appliance': t['name'], 'per_hour_units': per_hour_units, 'expected_cost': p * per_hour_units})
                block_str = ' → '.join(f'{int(h):02d}:00' for h in best['block'])
                summary_rows.append({'Appliance': t['name'], 'Schedule': block_str, 'Total units': t['units'], 'Estimated total cost': round(best['avg_price'] * float(t['units']), 3)})

            # Show summary table
            if summary_rows:
                st.write('Proposed schedules')
                st.dataframe(pd.DataFrame(summary_rows))

            # Stacked chart of scheduled appliances
            if schedule_rows:
                sched_df = pd.DataFrame(schedule_rows)
                sched_df = sched_df.sort_values('hour')
                fig_s = px.bar(
                    sched_df, x='hour', y='expected_cost', color='appliance',
                    labels={'expected_cost':('Expected cost' if using_cost else 'Cost index'), 'hour':'Hour of day', 'appliance': 'Appliance'},
                    title='Scheduled appliances by hour',
                )
                fig_s.update_layout(barmode='stack', xaxis=dict(tickmode='array', tickvals=list(range(24)), ticktext=[f'{h}:00' for h in range(24)]))
                st.plotly_chart(fig_s, use_container_width=True)

                # Download schedule CSV
                out_csv = sched_df[['hour','appliance','per_hour_units','expected_cost']].copy()
                out_csv['hour_display'] = out_csv['hour'].apply(lambda h: f'{int(h):02d}:00 - {int(h):02d}:59')
                csv_bytes_all = out_csv[['hour_display','appliance','per_hour_units','expected_cost']].to_csv(index=False).encode('utf-8')
                st.download_button('Download multi-appliance schedule (CSV)', data=csv_bytes_all, file_name='multi_appliance_schedule.csv', mime='text/csv')

st.markdown('---')
st.caption('If results look off, verify your CSV has a datetime column and a numeric consumption column. You can place the CSV in the project root and refresh the app.')
