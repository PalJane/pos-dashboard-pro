{
    'name': 'POS Dashboard Pro',
    'version': '18.0.1.0.0',
    'category': 'Point of Sale',
    'summary': 'Detailed Point of Sale analytics dashboard: sales, cashier performance, and multi-store comparison',
    'description': """
POS Dashboard Pro
==================
A detailed analytics dashboard for Point of Sale, including:
- Sales performance: revenue, top products, hourly trends
- Cashier/session performance: per-cashier stats, per-session breakdown
- Multi-store comparison: compare performance across POS locations
""",
    'author': 'Your Company',
    'website': 'https://yourwebsite.com',
    'support': 'support@paulasystems.org',
    'license': 'OPL-1',
    'depends': ['point_of_sale', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'pos_dashboard_pro/static/src/lib/chart.umd.js',
            'pos_dashboard_pro/static/src/js/**/*',
            'pos_dashboard_pro/static/src/xml/**/*',
            'pos_dashboard_pro/static/src/scss/**/*',
        ],
    },
    'images': ['static/description/banner.png'],
    'price': 88.00,
    'currency': 'USD',
    'installable': True,
    'application': True,
}
