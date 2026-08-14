from odoo import http
from odoo.http import request


class PosDashboardController(http.Controller):

    @http.route('/pos_dashboard_pro/data', type='json', auth='user')
    def get_dashboard_data(self, date_from=None, date_to=None, config_ids=None):
        """Return aggregated POS data for the dashboard.

        date_from / date_to: 'YYYY-MM-DD' strings
        config_ids: list of pos.config ids to filter by (for multi-store comparison)
        """
        Order = request.env['pos.order']
        domain = [('state', 'in', ['paid', 'done', 'invoiced'])]

        if date_from:
            domain.append(('date_order', '>=', date_from))
        if date_to:
            domain.append(('date_order', '<=', date_to))
        if config_ids:
            domain.append(('config_id', 'in', config_ids))

        orders = Order.search(domain)

        # --- Sales performance ---
        total_revenue = sum(orders.mapped('amount_total'))
        total_orders = len(orders)
        avg_order_value = total_revenue / total_orders if total_orders else 0

        # Top products
        lines = request.env['pos.order.line'].search([('order_id', 'in', orders.ids)])
        product_sales = {}
        for line in lines:
            key = line.product_id.id
            if key not in product_sales:
                cost = line.product_id.standard_price or 0.0
                product_sales[key] = {
                    'name': line.product_id.display_name,
                    'qty': 0.0,
                    'revenue': 0.0,
                    'cost': 0.0,
                }
            product_sales[key]['qty'] += line.qty
            product_sales[key]['revenue'] += line.price_subtotal_incl
            product_sales[key]['cost'] += (line.product_id.standard_price or 0.0) * line.qty
        for p in product_sales.values():
            p['margin'] = round(p['revenue'] - p['cost'], 2)
            p['margin_pct'] = round((p['margin'] / p['revenue'] * 100), 1) if p['revenue'] else 0.0
        top_products = sorted(product_sales.values(), key=lambda p: p['revenue'], reverse=True)[:10]
        top_margin_products = sorted(
            [p for p in product_sales.values() if p['margin'] > 0],
            key=lambda p: p['margin'], reverse=True
        )[:20]

        # Overall margin summary
        total_cost = sum(p['cost'] for p in product_sales.values())
        total_margin = round(total_revenue - total_cost, 2)
        total_margin_pct = round((total_margin / total_revenue * 100), 1) if total_revenue else 0.0

        # Hourly trend
        hourly = {h: 0.0 for h in range(24)}
        for order in orders:
            if order.date_order:
                hourly[order.date_order.hour] += order.amount_total
        hourly_trend = [{'hour': h, 'revenue': round(v, 2)} for h, v in sorted(hourly.items())]

        # Daily trend
        daily = {}
        for order in orders:
            if order.date_order:
                d = order.date_order.strftime('%Y-%m-%d')
                daily[d] = daily.get(d, 0.0) + order.amount_total
        daily_trend = [{'date': d, 'revenue': round(v, 2)} for d, v in sorted(daily.items())]

        # Monthly trend
        monthly = {}
        for order in orders:
            if order.date_order:
                m = order.date_order.strftime('%Y-%m')
                monthly[m] = monthly.get(m, 0.0) + order.amount_total
        monthly_trend = [{'month': m, 'revenue': round(v, 2)} for m, v in sorted(monthly.items())]

        # Yearly trend
        yearly = {}
        for order in orders:
            if order.date_order:
                y = order.date_order.strftime('%Y')
                yearly[y] = yearly.get(y, 0.0) + order.amount_total
        yearly_trend = [{'year': y, 'revenue': round(v, 2)} for y, v in sorted(yearly.items())]

        # --- Cashier / session performance ---
        cashier_stats = {}
        for order in orders:
            cashier = order.user_id
            key = cashier.id
            if key not in cashier_stats:
                cashier_stats[key] = {'name': cashier.name, 'orders': 0, 'revenue': 0.0}
            cashier_stats[key]['orders'] += 1
            cashier_stats[key]['revenue'] += order.amount_total
        cashier_performance = sorted(cashier_stats.values(), key=lambda c: c['revenue'], reverse=True)

        Session = request.env['pos.session']
        session_domain = [('state', 'in', ['closed', 'closing_control'])]
        if config_ids:
            session_domain.append(('config_id', 'in', config_ids))
        sessions = Session.search(session_domain, limit=20, order='stop_at desc')
        session_performance = [{
            'name': s.name,
            'config': s.config_id.name,
            'cashier': s.user_id.name,
            'start': s.start_at and s.start_at.strftime('%Y-%m-%d %H:%M') or '',
            'stop': s.stop_at and s.stop_at.strftime('%Y-%m-%d %H:%M') or '',
            'total_orders': len(s.order_ids),
            'total_revenue': round(sum(s.order_ids.mapped('amount_total')), 2),
            'cash_difference': round(s.cash_register_difference, 2) if hasattr(s, 'cash_register_difference') else 0.0,
        } for s in sessions]

        # --- Multi-store comparison ---
        store_stats = {}
        for order in orders:
            cfg = order.config_id
            key = cfg.id
            if key not in store_stats:
                store_stats[key] = {'name': cfg.name, 'orders': 0, 'revenue': 0.0}
            store_stats[key]['orders'] += 1
            store_stats[key]['revenue'] += order.amount_total
        store_comparison = sorted(store_stats.values(), key=lambda s: s['revenue'], reverse=True)

        # --- Per-terminal performance over time (daily series per config) ---
        daily_by_config = {}
        for order in orders:
            cfg = order.config_id
            day = order.date_order.strftime('%Y-%m-%d') if order.date_order else 'unknown'
            key = cfg.id
            if key not in daily_by_config:
                daily_by_config[key] = {'name': cfg.name, 'days': {}}
            daily_by_config[key]['days'].setdefault(day, 0.0)
            daily_by_config[key]['days'][day] += order.amount_total

        terminal_trends = []
        for cfg_id, info in daily_by_config.items():
            series = [{'date': d, 'revenue': round(v, 2)} for d, v in sorted(info['days'].items())]
            terminal_trends.append({'config_id': cfg_id, 'name': info['name'], 'series': series})

        all_configs = request.env['pos.config'].search_read([], ['id', 'name'])

        # --- Payments by method (merged by name across terminals) ---
        Payment = request.env['pos.payment']
        payments = Payment.search([('pos_order_id', 'in', orders.ids)])
        payment_stats = {}
        for pay in payments:
            key = pay.payment_method_id.name
            if key not in payment_stats:
                payment_stats[key] = {'name': key, 'amount': 0.0, 'count': 0}
            payment_stats[key]['amount'] += pay.amount
            payment_stats[key]['count'] += 1
        payment_methods = sorted(payment_stats.values(), key=lambda p: p['amount'], reverse=True)

        # --- Payments by method, broken down per terminal ---
        payment_by_terminal = {}
        for pay in payments:
            cfg_name = pay.pos_order_id.config_id.name
            method_name = pay.payment_method_id.name
            key = (cfg_name, method_name)
            if key not in payment_by_terminal:
                payment_by_terminal[key] = {'config': cfg_name, 'method': method_name, 'amount': 0.0, 'count': 0}
            payment_by_terminal[key]['amount'] += pay.amount
            payment_by_terminal[key]['count'] += 1
        payment_methods_by_terminal = sorted(
            payment_by_terminal.values(), key=lambda p: (p['config'], -p['amount'])
        )

        return {
            'summary': {
                'total_revenue': round(total_revenue, 2),
                'total_orders': total_orders,
                'avg_order_value': round(avg_order_value, 2),
                'total_cost': round(total_cost, 2),
                'total_margin': total_margin,
                'total_margin_pct': total_margin_pct,
            },
            'top_products': top_products,
            'top_margin_products': top_margin_products,
            'payment_methods': payment_methods,
            'payment_methods_by_terminal': payment_methods_by_terminal,
            'hourly_trend': hourly_trend,
            'daily_trend': daily_trend,
            'monthly_trend': monthly_trend,
            'yearly_trend': yearly_trend,
            'cashier_performance': cashier_performance,
            'session_performance': session_performance,
            'store_comparison': store_comparison,
            'terminal_trends': terminal_trends,
            'all_configs': all_configs,
        }
