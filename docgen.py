import os
import re
import zipfile
import shutil
import tempfile
import logging
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates_docs')


def _get_template(template_name):
    path = os.path.join(TEMPLATES_DIR, template_name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template not found: {path}")
    return path


def _replace_in_ods(template_path, replacements):
    with zipfile.ZipFile(template_path, 'r') as zin:
        content = zin.read('content.xml')
        entries = [(item, zin.read(item.filename)) for item in zin.infolist()]

    text = content.decode('utf-8')
    for key, value in replacements.items():
        text = text.replace(key, value)
    text = re.sub(r'\{[A-Za-z0-9_]+\}', ' ', text)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.ods')
    os.close(tmp_fd)
    with zipfile.ZipFile(tmp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item, data in entries:
            if item.filename == 'content.xml':
                zout.writestr(item, text.encode('utf-8'))
            else:
                zout.writestr(item, data)

    return tmp_path


def _extract_task_data(task):
    text = ''
    if task:
        text = (task.get('name') or '') + '\n' + (task.get('description') or '')
    import re
    data = {}
    m = re.search(r'№\s*(\S+)', text)
    data['number'] = m.group(1) if m else ''
    m = re.search(r'(\d+)-Пятерочка', text)
    data['shop'] = m.group(1) if m else ''
    m = re.search(r'SAP[:\s]*(\S+)', text)
    data['sap'] = m.group(1) if m else ''
    m = re.search(r'(Модель ККТ|Модель ФН)[:\s]*([^\n]+)', text)
    data['model'] = m.group(2).strip() if m else ''
    m = re.search(r'Зав\.№ ККТ[:\s]*(\S+)', text)
    data['kkt'] = m.group(1) if m else ''
    m = re.search(r'Адрес[:\s]*([^\n]+)', text)
    data['address'] = m.group(1).strip() if m else ''
    m = re.search(r'Код заявки[:\s]*(\S+)', text)
    data['code'] = m.group(1) if m else ''
    return data


def _read_ods_text(template_path):
    with zipfile.ZipFile(template_path, 'r') as z:
        content = z.read('content.xml').decode('utf-8')
    return content


def _make_replacements(task_data, profile_name='', extra=None):
    now = __import__('datetime').datetime.now()
    d = now.strftime('%d')
    m = now.strftime('%m')
    y = now.strftime('%Y')
    r = {
        '{KA}': profile_name or '',
        '{DATE}': now.strftime('%d.%m.%Y'),
        '{IN}': task_data.get('code', ''),
        '{D1}': d[0], '{D0}': d[1],
        '{M1}': m[0], '{M0}': m[1],
        '{Y3}': y[0], '{Y2}': y[1], '{Y1}': y[2], '{Y0}': y[3],
        '{MVZ}': 'X0UGSMP4',
        '{RVR}': task_data.get('rvr', ''),
        '{DOP}': task_data.get('dop', ''),
        '{DESC}': task_data.get('desc', ''),
        '{ZD}': task_data.get('zd', ''),
    }
    shop = task_data.get('shop', '')
    sap = task_data.get('sap', '')
    r['{SHOP}'] = shop
    r['{SAP}'] = sap
    r['{ADDR}'] = task_data.get('address', '')
    r['{NUM}'] = shop
    if shop:
        ps = shop.rjust(5)
        r['{N0}'] = ps[0]; r['{N1}'] = ps[1]; r['{N2}'] = ps[2]; r['{N3}'] = ps[3]; r['{N4}'] = ps[4]
    else:
        for i in range(5): r[f'{{N{i}}}'] = '_'
    if sap:
        ps = sap.ljust(4)[:4]
        r['{S0}'] = ps[0]; r['{S1}'] = ps[1]; r['{S2}'] = ps[2]; r['{S3}'] = ps[3]
    else:
        for i in range(4): r[f'{{S{i}}}'] = '_'
    if extra:
        for k, v in extra.items():
            if k != 'items':
                r[f'{{{k.upper()}}}'] = str(v)
    return r


def _doc_filename(suffix, task_data):
    ts = __import__('datetime').datetime.now().strftime('%Y.%m.%d_%H.%M')
    sap = task_data.get('sap', '')
    shop = task_data.get('shop', '')
    code = task_data.get('code', '')
    parts = [p for p in [ts, sap, shop, code, suffix] if p]
    return '-'.join(parts) + '.ods'


def _fill_item_rows(replacements, items, max_rows=10):
    for i, item in enumerate(items[:max_rows], 1):
        name = item.get('name', '')
        series = item.get('series', '')
        replacements[f'{{TV{i}}}'] = name
        replacements[f'{{SN{i}}}'] = series
        replacements[f'{{DS{i}}}'] = (name + ' ' + series).strip()
    for i in range(len(items) + 1, max_rows + 1):
        replacements.setdefault(f'{{TV{i}}}', ' ')
        replacements.setdefault(f'{{SN{i}}}', ' ')
        replacements.setdefault(f'{{DS{i}}}', ' ')


def generate_act(data):
    task = data.get('task', {})
    profile_name = data.get('profileName', '')
    extra = data.get('fields', {})
    task_data = _extract_data_from_text(task, profile_name)
    task_data.update(extra)
    replacements = _make_replacements(task_data, profile_name, extra)

    items = extra.get('items', [])
    _fill_item_rows(replacements, items, 10)
    if len(items) > 7:
        for key in list(replacements.keys()):
            if key.startswith('{DS') or key.startswith('{DN'):
                replacements[key] = ''
        replacements['{DS1}'] = 'Оборудование согласно форме документа М15'

    template_path = _get_template('АВР.ods')
    result_path = _replace_in_ods(template_path, replacements)
    return _read_result(result_path, _doc_filename('AVR', task_data))


def generate_fn(data):
    task = data.get('task', {})
    profile_name = data.get('profileName', '')
    extra = data.get('fields', {})
    task_data = _extract_data_from_text(task, profile_name)
    task_data.update(extra)
    replacements = _make_replacements(task_data, profile_name, extra)

    template_path = _get_template('ФН.ods')
    result_path = _replace_in_ods(template_path, replacements)
    return _read_result(result_path, _doc_filename('FN', task_data))


def generate_m15(data):
    task = data.get('task', {})
    profile_name = data.get('profileName', '')
    is_reverse = data.get('reverse', False)
    extra = data.get('fields', {})
    task_data = _extract_data_from_text(task, profile_name)
    task_data.update(extra)
    replacements = _make_replacements(task_data, profile_name, extra)

    items = extra.get('items', [])
    _fill_item_rows(replacements, items, 10)

    template_name = 'M15_Обратная.ods' if is_reverse else 'M15_Прямая.ods'
    template_path = _get_template(template_name)
    result_path = _replace_in_ods(template_path, replacements)
    return _read_result(result_path, _doc_filename('M15', task_data))


def generate_documents(data):
    results = {}
    include_act = data.get('includeAct', False)
    include_fn = data.get('includeFn', False)
    include_m15 = data.get('includeM15', False)

    if include_act:
        results['act'] = generate_act(data)
    if include_fn:
        results['fn'] = generate_fn(data)
    if include_m15:
        results['m15'] = generate_m15(data)
    return results


def _extract_data_from_text(task, profile_name=''):
    text = ''
    if task:
        text = (task.get('name') or '') + '\n' + (task.get('description') or '')
    import re
    data = {}
    m = re.search(r'(\d+)-Пятерочка', text)
    data['shop'] = m.group(1) if m else ''
    m = re.search(r'SAP[:\s]*(\S+)', text)
    data['sap'] = m.group(1) if m else ''
    m = re.search(r'Адрес[:\s]*([^\n]+)', text)
    data['address'] = m.group(1).strip() if m else ''
    m = re.search(r'(\d{6,7})', task.get('number', ''))
    data['number'] = m.group(1) if m else task.get('number', '')
    data['code'] = task.get('guid', '')[:8] if task else ''
    return data


def _read_result(filepath, filename):
    return {
        'path': filepath,
        'filename': filename,
        'mime': 'application/vnd.oasis.opendocument.spreadsheet',
    }