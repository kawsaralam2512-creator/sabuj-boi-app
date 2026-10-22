"""
🛣️ সবুজ বই — Routes Module
============================================
সব Flask routes এখানে register হয়।
"""

import copy
import json
import re
from datetime import datetime
from pathlib import Path
from flask import (
    render_template, request, jsonify, redirect, url_for,
    session, flash, send_from_directory, abort
)

from app import (
    load_json, save_json, login_required,
    normalize_for_search, bn_to_en, en_to_bn,
    make_cross_references_clickable
)


# ==================== 🔍 Search Scoring Helpers ====================
def calculate_relevance_score(text, query_words, phrase=""):
    if not text or not query_words:
        return 0

    text_norm = normalize_for_search(text)
    score = 0

    if phrase and len(query_words) > 1:
        phrase_norm = normalize_for_search(phrase)
        if phrase_norm in text_norm:
            score += 500
        else:
            positions = []
            for w in query_words:
                pos = text_norm.find(w)
                if pos >= 0:
                    positions.append(pos)
            if len(positions) == len(query_words):
                span = max(positions) - min(positions)
                if span < 100:
                    score += 300
                elif span < 300:
                    score += 150

    matched_words = 0
    partial_matches = 0

    for word in query_words:
        if word in text_norm:
            matched_words += 1
            count = text_norm.count(word)
            score += min(count * 15, 60)
        else:
            if len(word) >= 5:
                partial = word[:max(4, len(word) - 1)]
                if partial in text_norm:
                    partial_matches += 1
                    score += 15

    if matched_words == len(query_words):
        score += 500
    elif matched_words >= max(1, len(query_words) - 1):
        score += matched_words * 40
    elif matched_words == 0 and partial_matches == 0:
        return 0
    else:
        score += matched_words * 10

    return score


def calculate_title_score(title, query_words, phrase=""):
    if not title or not query_words:
        return 0

    title_norm = normalize_for_search(title)
    score = 0

    if phrase and len(query_words) > 1:
        phrase_norm = normalize_for_search(phrase)
        if phrase_norm in title_norm:
            score += 2000
        elif title_norm.startswith(phrase_norm[:10]):
            score += 500

    matched = 0
    for w in query_words:
        if w in title_norm:
            matched += 1
        elif len(w) >= 5 and w[:4] in title_norm:
            matched += 0.5

    if matched == len(query_words):
        score += 800
    elif matched >= len(query_words) - 1:
        score += int(matched * 100)
    elif matched > 0:
        score += int(matched * 30)

    return score


# ==================== 🎯 Stats Helper ====================
def get_stats(app):
    book_data = load_json(app.config['BOOK_FILE'])
    misc_data = load_json(app.config['MISC_FILE'])
    systems_data = load_json(app.config['SYSTEMS_FILE'])
    challenges_data = load_json(app.config['CHALLENGES_FILE'])
    milestones_data = load_json(app.config['MILESTONES_FILE'])
    funds_data = load_json(app.config['FUNDS_FILE'])
    decision_data = load_json(app.config['DECISION_FILE'])
    ppr_data = load_json(app.config['PPR_FILE'])
    appendix_data = load_json(app.config.get('APPENDIX_FILE', ''))

    total_sections = sum(len(c.get('sections', [])) for c in book_data.get('chapters', []))
    total_subsections = 0
    for chapter in book_data.get('chapters', []):
        for section in chapter.get('sections', []):
            total_subsections += len(section.get('subsections', []))
    total_problems = sum(len(cat.get('problems', [])) for cat in decision_data.get('categories', []))

    return {
        'chapters': len(book_data.get('chapters', [])),
        'sections': total_sections,
        'subsections': total_subsections,
        'misc': len(misc_data.get('entries', [])),
        'systems': len(systems_data.get('systems', [])),
        'challenges': len(challenges_data.get('challenges', [])),
        'milestones': len(milestones_data.get('milestones', [])),
        'funds': len(funds_data.get('sections', [])),
        'problems': total_problems,
        'ppr': len(ppr_data.get('problems', [])),
        'appendices': len(appendix_data.get('appendices', [])),
    }


# ==================== 🏠 Main Routes ====================
def register_routes(app):

    @app.route('/')
    def index():
        book_data = load_json(app.config['BOOK_FILE'])
        return render_template('index.html', book=book_data, chapters=book_data.get('chapters', []), stats=get_stats(app))

    # ==================== 📱 PWA Routes ====================
    @app.route('/manifest.json')
    def serve_manifest():
        return send_from_directory(app.static_folder, 'manifest.json')

    @app.route('/service-worker.js')
    def serve_sw():
        response = send_from_directory(app.static_folder, 'service-worker.js')
        response.headers['Content-Type'] = 'application/javascript'
        response.headers['Service-Worker-Allowed'] = '/'
        return response

    # ==================== 🔍 Global Search ====================
    @app.route('/search')
    def search():
        query = request.args.get('q', '').strip()
        wants_html = request.args.get('format', '') != 'json'

        if not query or len(query) < 2:
            if wants_html:
                return render_template('search.html', query=query, results=[])
            return jsonify([])

        phrase = query
        query_norm = normalize_for_search(query)
        words = query_norm.split()

        book_data = load_json(app.config['BOOK_FILE'])
        misc_data = load_json(app.config['MISC_FILE'])
        systems_data = load_json(app.config['SYSTEMS_FILE'])
        challenges_data = load_json(app.config['CHALLENGES_FILE'])
        milestones_data = load_json(app.config['MILESTONES_FILE'])
        funds_data = load_json(app.config['FUNDS_FILE'])
        decision_data = load_json(app.config['DECISION_FILE'])
        ppr_data = load_json(app.config['PPR_FILE'])
        appendix_data = load_json(app.config.get('APPENDIX_FILE', ''))

        results = []

        if re.match(r'^[০-৯\d]+(\.[০-৯\d]+)+$', query.strip()):
            ref_query = query.strip()
            ref_en = bn_to_en(ref_query)
            ref_bn = en_to_bn(ref_query)

            for chapter in book_data.get('chapters', []):
                for idx, section in enumerate(chapter.get('sections', [])):
                    section_ref = section.get('ref', '')
                    if (bn_to_en(section_ref) == ref_en or en_to_bn(section_ref) == ref_bn or section_ref in [ref_query, ref_bn, ref_en]):
                        results.append({
                            'type': 'ref', 'score': 10000, 'chapter': chapter.get('title', ''),
                            'section': f"📖 অনুচ্ছেদ {section_ref}: {section.get('heading', '')}",
                            'snippet': section.get('details', '')[:250], 'page': chapter.get('page', ''),
                            'url': f'/section/{chapter.get("id")}/{idx}'
                        })
            if results:
                if wants_html:
                    return render_template('search.html', query=query, results=results[:20])
                return jsonify(results[:15])

        # বই
        for chapter in book_data.get('chapters', []):
            for idx, section in enumerate(chapter.get('sections', [])):
                heading = section.get('heading', '')
                details = section.get('details', '')
                ref = section.get('ref', '')
                subs_text = ' '.join(s.get('text', '') for s in section.get('subsections', []))
                combined = f"{ref} {heading} {details} {subs_text}"
                total_score = calculate_relevance_score(combined, words, phrase) + calculate_title_score(heading, words, phrase)
                if total_score > 0:
                    has_subs = bool(section.get('subsections'))
                    results.append({
                        'type': 'book', 'score': total_score, 'chapter': chapter.get('title', ''),
                        'section': f"{'[' + ref + '] ' if ref else ''}{heading}{' 📌' if has_subs else ''}",
                        'snippet': details[:250] + ('...' if len(details) > 250 else ''),
                        'page': chapter.get('page', ''), 'url': f'/section/{chapter.get("id")}/{idx}'
                    })
                if section.get('subsections'):
                    section_ref_bn = en_to_bn(ref)
                    for sub_idx, sub in enumerate(section['subsections']):
                        sub_text = sub.get('text', '')
                        sub_score = calculate_relevance_score(sub_text, words, phrase)
                        if sub_score > 0:
                            sub_ref = f"{section_ref_bn}.{en_to_bn(str(sub_idx + 1))}"
                            results.append({
                                'type': 'subsection', 'score': sub_score + 5, 'chapter': chapter.get('title', ''),
                                'section': f"📌 উপানুচ্ছেদ {sub_ref}: {sub_text[:80]}...",
                                'snippet': sub_text[:250], 'page': chapter.get('page', ''),
                                'url': f'/section/{chapter.get("id")}/{idx}#sub-{sub_idx + 1}'
                            })

        # বিবিধ
        for entry in misc_data.get('entries', []):
            combined = f"{entry.get('problem', '')} {entry.get('solution', '')}"
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(entry.get('problem', ''), words, phrase)
            if total > 0:
                results.append({
                    'type': 'misc', 'score': total, 'chapter': '📝 বিবিধ', 'section': entry.get('problem', ''),
                    'snippet': entry.get('solution', '')[:250], 'page': '', 'url': f'/misc/view/{entry.get("id")}'
                })

        # সিস্টেম
        for sys in systems_data.get('systems', []):
            combined = f"{sys.get('name', '')} {sys.get('bangla_name', '')} {sys.get('purpose', '')}"
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(f"{sys.get('name', '')} {sys.get('bangla_name', '')}", words, phrase)
            if total > 0:
                results.append({
                    'type': 'system', 'score': total, 'chapter': '🖥️ সরকারি সিস্টেম', 'section': f"{sys.get('name', '')} — {sys.get('bangla_name', '')}",
                    'snippet': sys.get('purpose', '')[:250], 'page': '', 'url': f'/system/{sys.get("id")}'
                })

        # চ্যালেঞ্জ
        for ch in challenges_data.get('challenges', []):
            combined = ' '.join([ch.get('problem', ''), ch.get('solution', ''), ch.get('symptom', ''), ch.get('consequence', '')])
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(ch.get('problem', ''), words, phrase)
            if total > 0:
                results.append({
                    'type': 'challenge', 'score': total, 'chapter': f"⚠️ চ্যালেঞ্জ ({ch.get('phase', '')})", 'section': ch.get('problem', ''),
                    'snippet': ch.get('solution', '')[:250], 'page': '', 'url': f'/challenge/{ch.get("id")}'
                })

        # অনুমোদন
        for ms in milestones_data.get('milestones', []):
            combined = f"{ms.get('category', '')} {ms.get('limit', '')} {ms.get('approver', '')}"
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(ms.get('category', ''), words, phrase)
            if total > 0:
                results.append({
                    'type': 'milestone', 'score': total, 'chapter': '🎯 অনুমোদনের সীমা', 'section': f"{ms.get('category', '')} — {ms.get('limit', '')}",
                    'snippet': f"অনুমোদনকারী: {ms.get('approver', '')}", 'page': '', 'url': f'/milestone/{ms.get("id")}'
                })

        # অর্থ
        for fs in funds_data.get('sections', []):
            points_text = ' '.join(f"{p.get('subtitle', '')} {p.get('details', '')}" for p in fs.get('points', []))
            combined = f"{fs.get('title', '')} {fs.get('content', '')} {points_text}"
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(fs.get('title', ''), words, phrase)
            if total > 0:
                results.append({
                    'type': 'fund', 'score': total, 'chapter': '💰 অর্থ ব্যবস্থাপনা', 'section': fs.get('title', ''),
                    'snippet': fs.get('content', '')[:250], 'page': '', 'url': f'/funds#fund-{fs.get("id")}'
                })

        # সিদ্ধান্ত
        for cat in decision_data.get('categories', []):
            for prob in cat.get('problems', []):
                combined = f"{prob.get('question', '')} {prob.get('solution', '')}"
                total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(prob.get('question', ''), words, phrase)
                if total > 0:
                    results.append({
                        'type': 'decision', 'score': total, 'chapter': f"🌳 {cat.get('name', '')}", 'section': prob.get('question', ''),
                        'snippet': prob.get('solution', '')[:250], 'page': '', 'url': f'/decision#problem-{prob.get("id")}'
                    })

        # PPR
        for p in ppr_data.get('problems', []):
            combined = ' '.join([str(p.get('problem', '')), str(p.get('solution', '')), str(p.get('rule_title', '')), ' '.join(p.get('keywords', []))])
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(p.get('problem', ''), words, phrase)
            if total > 0:
                page_info = f" — পৃষ্ঠা {p.get('pdf_page')}" if p.get('pdf_page') else ""
                results.append({
                    'type': 'ppr', 'score': total, 'chapter': f"📕 পিপিআর ২০২৫ — {p.get('chapter', '')}",
                    'section': f"বিধি {p.get('rule', '')} {p.get('sub_rule', '')}: {p.get('problem', '')}",
                    'snippet': p.get('solution', '')[:250] + page_info, 'page': str(p.get('pdf_page', '')), 'url': f"/ppr/view/{p.get('id')}"
                })

        # সংযোজনী
        for ap in appendix_data.get('appendices', []):
            combined = f"{ap.get('name', '')} {ap.get('title', '')} {ap.get('description', '')} {' '.join(ap.get('keywords', []))}"
            total = calculate_relevance_score(combined, words, phrase) + calculate_title_score(f"{ap.get('name', '')} {ap.get('title', '')}", words, phrase)
            if total > 0:
                results.append({
                    'type': 'appendix', 'score': total, 'chapter': '📎 সংযোজনী', 'section': f"{ap.get('name', '')} — {ap.get('title', '')}",
                    'snippet': ap.get('description', '')[:250], 'page': f"{ap.get('page_start', '')}–{ap.get('page_end', '')}", 'url': f"/appendix/{ap.get('id')}"
                })

        # Sort + Filter
        results.sort(key=lambda x: x.get('score', 0), reverse=True)
        if results:
            max_score = results[0].get('score', 0)
            min_threshold = max_score * 0.15
            results = [r for r in results if r.get('score', 0) >= min_threshold][:20]

        if wants_html:
            return render_template('search.html', query=query, results=results)
        return jsonify(results)

    # ==================== 📖 Chapter ====================
    @app.route('/chapter/<int:chapter_id>')
    def chapter_detail(chapter_id):
        book_data = load_json(app.config['BOOK_FILE'])
        chapter = next((c for c in book_data.get('chapters', []) if c.get('id') == chapter_id), None)
        if not chapter:
            flash('❌ অধ্যায় পাওয়া যায়নি', 'error')
            return redirect(url_for('index'))

        chapter_copy = copy.deepcopy(chapter)
        existing_refs = {s.get('ref') for s in chapter_copy.get('sections', []) if s.get('ref')}
        auto_counter = 1
        for section in chapter_copy.get('sections', []):
            if not section.get('ref'):
                auto_ref = f"{chapter_id}.{auto_counter}"
                while auto_ref in existing_refs:
                    auto_counter += 1
                    auto_ref = f"{chapter_id}.{auto_counter}"
                section['ref'] = auto_ref
                section['is_auto_ref'] = True
                existing_refs.add(auto_ref)
                auto_counter += 1

        return render_template('chapter.html', chapter=chapter_copy, book=book_data)

    # ==================== 📄 Section ====================
    @app.route('/section/<int:chapter_id>/<int:section_index>')
    def section_detail(chapter_id, section_index):
        book_data = load_json(app.config['BOOK_FILE'])
        chapter = next((c for c in book_data.get('chapters', []) if c.get('id') == chapter_id), None)
        if not chapter:
            flash('❌ অধ্যায় পাওয়া যায়নি', 'error')
            return redirect(url_for('index'))

        sections = chapter.get('sections', [])
        if section_index < 0 or section_index >= len(sections):
            flash('❌ সেকশন পাওয়া যায়নি', 'error')
            return redirect(url_for('chapter_detail', chapter_id=chapter_id))

        section = copy.deepcopy(sections[section_index])
        section['details_html'] = make_cross_references_clickable(section.get('details', ''))

        if section.get('subsections'):
            section_ref_bn = section.get('ref', '')
            if any(c in '0123456789' for c in section_ref_bn):
                section_ref_bn = en_to_bn(section_ref_bn)
            for sub_idx, sub in enumerate(section['subsections']):
                sub['text_html'] = make_cross_references_clickable(sub.get('text', ''))
                sub['display_ref'] = f"{section_ref_bn}.{en_to_bn(str(sub_idx + 1))}"

        return render_template('section.html', chapter=chapter, section=section, section_index=section_index)

    # ==================== 📄 PDF Viewer (Section) ====================
    @app.route('/pdf/view/<int:chapter_id>/<int:section_index>')
    def section_pdf_view(chapter_id, section_index):
        book_data = load_json(app.config['BOOK_FILE'])
        chapter = next((c for c in book_data.get('chapters', []) if c.get('id') == chapter_id), None)
        
        if not chapter:
            flash('❌ অধ্যায় পাওয়া যায়নি', 'error')
            return redirect(url_for('index'))
        
        sections = chapter.get('sections', [])
        if section_index < 0 or section_index >= len(sections):
            flash('❌ সেকশন পাওয়া যায়নি', 'error')
            return redirect(url_for('chapter_detail', chapter_id=chapter_id))
            
        section = sections[section_index]
        page = chapter.get('page', 1)
        
        return render_template(
            'pdf_viewer.html',
            pdf_url=url_for('static', filename='pdfs/sabuj_boi_2022.pdf'),
            page=page,
            pdf_title=f"অনুচ্ছেদ {section.get('ref', '')}: {section.get('heading', '')}",
            back_url=url_for('section_detail', chapter_id=chapter_id, section_index=section_index)
        )

    # ==================== 🔢 Smart Lookup ====================
    @app.route('/lookup/<path:ref_number>')
    def lookup_reference(ref_number):
        book_data = load_json(app.config['BOOK_FILE'])
        ref_orig = ref_number.strip()
        ref_en = bn_to_en(ref_orig)
        ref_bn = en_to_bn(ref_orig)
        possible_refs = {ref_orig, ref_en, ref_bn}

        for chapter in book_data.get('chapters', []):
            for idx, section in enumerate(chapter.get('sections', [])):
                section_ref = section.get('ref', '')
                if not section_ref:
                    continue
                if (section_ref in possible_refs or bn_to_en(section_ref) in possible_refs or en_to_bn(section_ref) in possible_refs):
                    return redirect(url_for('section_detail', chapter_id=chapter['id'], section_index=idx))

        for chapter in book_data.get('chapters', []):
            for idx, section in enumerate(chapter.get('sections', [])):
                section_ref = section.get('ref', '')
                if not section_ref:
                    continue
                section_ref_bn = en_to_bn(section_ref)
                for sub_idx, sub in enumerate(section.get('subsections', [])):
                    sub_ref_bn = f"{section_ref_bn}.{en_to_bn(str(sub_idx + 1))}"
                    if sub_ref_bn in possible_refs or bn_to_en(sub_ref_bn) in possible_refs:
                        return redirect(url_for('section_detail', chapter_id=chapter['id'], section_index=idx) + f'#sub-{sub_idx + 1}')

        ref_en_parts = ref_en.split('.')
        if ref_en_parts:
            first_part = ref_en_parts[0]
            try:
                chapter_id_from_ref = int(first_part)
                for chapter in book_data.get('chapters', []):
                    if chapter.get('id') == chapter_id_from_ref:
                        for idx, section in enumerate(chapter.get('sections', [])):
                            if bn_to_en(section.get('ref', '')).startswith(first_part + '.'):
                                flash(f'📖 অনুচ্ছেদ {ref_orig} সরাসরি পাওয়া যায়নি। Chapter {en_to_bn(first_part)}-এ নিয়ে যাওয়া হয়েছে।', 'success')
                                return redirect(url_for('section_detail', chapter_id=chapter['id'], section_index=idx))
            except (ValueError, IndexError):
                pass

        for chapter in book_data.get('chapters', []):
            for idx, section in enumerate(chapter.get('sections', [])):
                heading = section.get('heading', '')
                if ref_en in bn_to_en(heading) or ref_bn in heading or ref_orig in heading:
                    return redirect(url_for('section_detail', chapter_id=chapter['id'], section_index=idx))

        try:
            chapter_num = int(ref_en_parts[0]) if ref_en_parts else 0
            if chapter_num > 0:
                for chapter in book_data.get('chapters', []):
                    if chapter.get('id') == chapter_num:
                        flash(f'📖 অনুচ্ছেদ {ref_orig} পাওয়া যায়নি। Chapter {en_to_bn(str(chapter_num))}-এ নিয়ে যাওয়া হয়েছে।', 'error')
                        return redirect(url_for('chapter_detail', chapter_id=chapter_num))
        except (ValueError, IndexError):
            pass

        flash(f'❌ অনুচ্ছেদ {ref_orig} পাওয়া যায়নি।', 'error')
        return redirect(url_for('index'))

    # ==================== 📎 Appendices ====================
    @app.route('/appendix')
    def appendix_page():
        appendices = load_json(app.config.get('APPENDIX_FILE', ''))
        return render_template('appendix.html', appendices=appendices)

    @app.route('/appendix/<appendix_id>')
    def appendix_detail(appendix_id):
        appendices = load_json(app.config.get('APPENDIX_FILE', ''))
        ap = next((a for a in appendices.get('appendices', []) if a.get('id') == appendix_id), None)
        if not ap:
            flash('❌ সংযোজনী পাওয়া যায়নি', 'error')
            return redirect(url_for('appendix_page'))
        return render_template('appendix_detail.html', appendix=ap, pdf_file=appendices.get('pdf_file', 'sabuj_boi_2022.pdf'))

    # ==================== 📌 All Refs ====================
    @app.route('/refs')
    def all_refs():
        book_data = load_json(app.config['BOOK_FILE'])
        refs_by_chapter = {}
        for chapter in book_data.get('chapters', []):
            chapter_refs = []
            for idx, section in enumerate(chapter.get('sections', [])):
                chapter_refs.append({
                    'ref': section.get('ref', '❌ নেই'),
                    'heading': section.get('heading', ''),
                    'url': f'/section/{chapter.get("id")}/{idx}',
                    'sub_count': len(section.get('subsections', [])),
                    'subsections': section.get('subsections', []),
                })
            refs_by_chapter[chapter['id']] = {'title': chapter.get('title', ''), 'refs': chapter_refs}
        return render_template('refs.html', refs=refs_by_chapter)

    # ==================== 🖥️ Systems ====================
    @app.route('/systems')
    def systems_page():
        systems_data = load_json(app.config['SYSTEMS_FILE'])
        return render_template('systems.html', systems=systems_data)

    @app.route('/system/<int:system_id>')
    def system_detail(system_id):
        systems_data = load_json(app.config['SYSTEMS_FILE'])
        system = next((s for s in systems_data.get('systems', []) if s.get('id') == system_id), None)
        if not system:
            flash('❌ সিস্টেম পাওয়া যায়নি', 'error')
            return redirect(url_for('systems_page'))
        return render_template('system_detail.html', system=system)

    # ==================== ⚠️ Challenges ====================
    @app.route('/challenges')
    def challenges_page():
        challenges_data = load_json(app.config['CHALLENGES_FILE'])
        phases = {}
        for ch in challenges_data.get('challenges', []):
            phases.setdefault(ch.get('phase', 'অন্যান্য'), []).append(ch)
        return render_template('challenges.html', challenges=challenges_data, phases=phases)

    @app.route('/challenge/<int:challenge_id>')
    def challenge_detail(challenge_id):
        """একটি নির্দিষ্ট চ্যালেঞ্জের বিস্তারিত পেজ (prev/next সহ)।"""
        challenges_data = load_json(app.config['CHALLENGES_FILE'])
        all_items = challenges_data.get('challenges', [])

        challenge = next((c for c in all_items if c.get('id') == challenge_id), None)
        if not challenge:
            abort(404)

        idx = all_items.index(challenge)
        prev_challenge = all_items[idx - 1] if idx > 0 else None
        next_challenge = all_items[idx + 1] if idx < len(all_items) - 1 else None

        return render_template(
            'challenge_detail.html',
            challenge=challenge,
            prev_challenge=prev_challenge,
            next_challenge=next_challenge,
        )

    # ==================== 🎯 Milestones ====================
    @app.route('/milestones')
    def milestones_page():
        milestones_data = load_json(app.config['MILESTONES_FILE'])
        return render_template('milestones.html', milestones=milestones_data)

    @app.route('/milestone/<int:milestone_id>')
    def milestone_detail(milestone_id):
        milestones_data = load_json(app.config['MILESTONES_FILE'])
        milestone = next((m for m in milestones_data.get('milestones', []) if m.get('id') == milestone_id), None)
        if not milestone:
            flash('❌ তথ্য পাওয়া যায়নি', 'error')
            return redirect(url_for('milestones_page'))
        return render_template('milestone_detail.html', milestone=milestone)

    # ==================== 💰 Funds ====================
    @app.route('/funds')
    def funds_page():
        funds_data = load_json(app.config['FUNDS_FILE'])
        return render_template('funds.html', funds=funds_data)

    # ==================== 🌳 Decision ====================
    @app.route('/decision')
    def decision_page():
        decision_data = load_json(app.config['DECISION_FILE'])
        return render_template('decision.html', decision=decision_data)

    # ==================== 📝 Misc ====================
    @app.route('/misc')
    def misc_page():
        misc_data = load_json(app.config['MISC_FILE'])
        return render_template('misc.html', misc=misc_data)

    @app.route('/misc/view/<int:entry_id>')
    def misc_detail(entry_id):
        misc_data = load_json(app.config['MISC_FILE'])
        entry = next((e for e in misc_data.get('entries', []) if e.get('id') == entry_id), None)
        if not entry:
            flash('❌ তথ্য পাওয়া যায়নি', 'error')
            return redirect(url_for('misc_page'))
        return render_template('misc_detail.html', entry=entry)

    @app.route('/misc/add', methods=['GET', 'POST'])
    @login_required
    def add_misc():
        if request.method == 'POST':
            problem = request.form.get('problem', '').strip()
            solution = request.form.get('solution', '').strip()
            if problem and solution:
                misc_data = load_json(app.config['MISC_FILE'])
                new_id = max((e.get('id', 0) for e in misc_data.get('entries', [])), default=0) + 1
                misc_data.setdefault('entries', []).append({
                    'id': new_id, 'problem': problem, 'solution': solution, 'date': datetime.now().strftime('%Y-%m-%d'),
                })
                if save_json(app.config['MISC_FILE'], misc_data):
                    flash('✅ নতুন তথ্য যোগ হয়েছে', 'success')
                else:
                    flash('❌ সংরক্ষণ ব্যর্থ হয়েছে', 'error')
                return redirect(url_for('misc_page'))
            else:
                flash('❌ সমস্যা ও সমাধান দুটোই পূরণ করুন', 'error')
        return render_template('add_misc.html')

    @app.route('/misc/delete/<int:entry_id>', methods=['POST'])
    @login_required
    def delete_misc(entry_id):
        misc_data = load_json(app.config['MISC_FILE'])
        misc_data['entries'] = [e for e in misc_data.get('entries', []) if e.get('id') != entry_id]
        if save_json(app.config['MISC_FILE'], misc_data):
            flash('🗑️ মুছে ফেলা হয়েছে', 'success')
        else:
            flash('❌ মুছে ফেলা ব্যর্থ', 'error')
        return redirect(url_for('misc_page'))

    @app.route('/misc/edit/<int:entry_id>', methods=['GET', 'POST'])
    @login_required
    def edit_misc(entry_id):
        misc_data = load_json(app.config['MISC_FILE'])
        entry = next((e for e in misc_data.get('entries', []) if e.get('id') == entry_id), None)
        if not entry:
            flash('❌ তথ্য পাওয়া যায়নি', 'error')
            return redirect(url_for('misc_page'))

        if request.method == 'POST':
            problem = request.form.get('problem', '').strip()
            solution = request.form.get('solution', '').strip()
            if problem and solution:
                entry['problem'] = problem
                entry['solution'] = solution
                entry['date'] = datetime.now().strftime('%Y-%m-%d')
                if save_json(app.config['MISC_FILE'], misc_data):
                    flash('✅ আপডেট হয়েছে', 'success')
                else:
                    flash('❌ আপডেট ব্যর্থ', 'error')
                return redirect(url_for('misc_page'))

        return render_template('edit_misc.html', entry=entry)

    # ==================== 📕 PPR 2025 ====================
    @app.route('/ppr')
    def ppr_page():
        ppr_data = load_json(app.config['PPR_FILE'])
        problems = ppr_data.get('problems', [])

        chapters_order = [
            'প্রথম অধ্যায়', 'দ্বিতীয় অধ্যায়', 'তৃতীয় অধ্যায়', 'চতুর্থ অধ্যায়', 'পঞ্চম অধ্যায়',
            'ষষ্ঠ অধ্যায়', 'সপ্তম অধ্যায়', 'অষ্টম অধ্যায়', 'নবম অধ্যায়'
        ]

        chapters = {}
        for p in problems:
            key = f"{p.get('chapter', 'অন্যান্য')} — {p.get('chapter_title', '')}".strip(' —')
            chapters.setdefault(key, []).append(p)

        sorted_chapters = {}
        for ch_name in chapters_order:
            for key in chapters:
                if key.startswith(ch_name):
                    sorted_chapters[key] = chapters[key]
        for key in chapters:
            if key not in sorted_chapters:
                sorted_chapters[key] = chapters[key]

        return render_template('ppr.html', ppr=ppr_data, problems=problems, chapters=sorted_chapters, problems_count=len(problems), chapters_count=len(sorted_chapters))

    @app.route('/ppr/view/<int:problem_id>')
    def ppr_problem_detail(problem_id):
        ppr_data = load_json(app.config['PPR_FILE'])
        problems = ppr_data.get('problems', [])
        problem = next((p for p in problems if p.get('id') == problem_id), None)
        if not problem:
            flash('❌ সমস্যাটি পাওয়া যায়নি', 'error')
            return redirect(url_for('ppr_page'))

        sorted_problems = sorted(problems, key=lambda x: x.get('id', 0))
        idx = next((i for i, p in enumerate(sorted_problems) if p.get('id') == problem_id), -1)
        prev_problem = sorted_problems[idx - 1] if idx > 0 else None
        next_problem = sorted_problems[idx + 1] if 0 <= idx < len(sorted_problems) - 1 else None
        position = f"{idx + 1} / {len(sorted_problems)}" if idx >= 0 else ""

        return render_template('ppr_viewer.html', ppr=ppr_data, problem=problem, prev_problem=prev_problem, next_problem=next_problem, position=position, pdf_file=app.config['PPR_PDF'])

    @app.route('/ppr/search')
    def ppr_search():
        query = request.args.get('q', '').strip()
        ppr_data = load_json(app.config['PPR_FILE'])
        problems = ppr_data.get('problems', [])

        if not query:
            chapters_order = [
                'প্রথম অধ্যায়', 'দ্বিতীয় অধ্যায়', 'তৃতীয় অধ্যায়', 'চতুর্থ অধ্যায়', 'পঞ্চম অধ্যায়',
                'ষষ্ঠ অধ্যায়', 'সপ্তম অধ্যায়', 'অষ্টম অধ্যায়', 'নবম অধ্যায়'
            ]
            chapters = {}
            for p in problems:
                key = f"{p.get('chapter', 'অন্যান্য')} — {p.get('chapter_title', '')}".strip(' —')
                chapters.setdefault(key, []).append(p)
            sorted_chapters = {}
            for ch_name in chapters_order:
                for key in chapters:
                    if key.startswith(ch_name):
                        sorted_chapters[key] = chapters[key]
            for key in chapters:
                if key not in sorted_chapters:
                    sorted_chapters[key] = chapters[key]
            return render_template('ppr.html', ppr=ppr_data, problems=problems, chapters=sorted_chapters, problems_count=len(problems), chapters_count=len(sorted_chapters))
        
        # =========================================================
        # 🚀 স্মার্ট অধ্যায় ফিল্টার (Smart Chapter Filter)
        # =========================================================
        chapter_map = {
            '1': 'প্রথম অধ্যায়', '১': 'প্রথম অধ্যায়', 'প্রথম': 'প্রথম অধ্যায়', '1st': 'প্রথম অধ্যায়',
            '2': 'দ্বিতীয় অধ্যায়', '২': 'দ্বিতীয় অধ্যায়', 'দ্বিতীয়': 'দ্বিতীয় অধ্যায়', '2nd': 'দ্বিতীয় অধ্যায়',
            '3': 'তৃতীয় অধ্যায়', '৩': 'তৃতীয় অধ্যায়', 'তৃতীয়': 'তৃতীয় অধ্যায়', '3rd': 'তৃতীয় অধ্যায়',
            '4': 'চতুর্থ অধ্যায়', '৪': 'চতুর্থ অধ্যায়', 'চতুর্থ': 'চতুর্থ অধ্যায়', '4th': 'চতুর্থ অধ্যায়',
            '5': 'পঞ্চম অধ্যায়', '৫': 'পঞ্চম অধ্যায়', 'পঞ্চম': 'পঞ্চম অধ্যায়', '5th': 'পঞ্চম অধ্যায়',
            '6': 'ষষ্ঠ অধ্যায়', '৬': 'ষষ্ঠ অধ্যায়', 'ষষ্ঠ': 'ষষ্ঠ অধ্যায়', '6th': 'ষষ্ঠ অধ্যায়',
            '7': 'সপ্তম অধ্যায়', '৭': 'সপ্তম অধ্যায়', 'সপ্তম': 'সপ্তম অধ্যায়', '7th': 'সপ্তম অধ্যায়',
            '8': 'অষ্টম অধ্যায়', '৮': 'অষ্টম অধ্যায়', 'অষ্টম': 'অষ্টম অধ্যায়', '8th': 'অষ্টম অধ্যায়',
            '9': 'নবম অধ্যায়', '৯': 'নবম অধ্যায়', 'নবম': 'নবম অধ্যায়', '9th': 'নবম অধ্যায়'
        }
        
        target_chapter = None
        for key, chapter_name in chapter_map.items():
            if key in query:
                target_chapter = chapter_name
                break
        
        if target_chapter:
            filtered_problems = [p for p in problems if target_chapter in str(p.get('chapter', ''))]
            
            # ইউজার যদি শুধু "২য় অধ্যায়" লিখে সার্চ করে, তবে সব রেজাল্ট দেখাবে (লিমিট ছাড়া)
            if len(query.split()) <= 3 and any(k in query for k in ['অধ্যায়', 'অধ্যায়', '১', '২', '৩', '৪', '৫', '৬', '৭', '৮', '৯', '1', '2', '3', '4', '5', '6', '7', '8', '9']):
                chapters_order = ['প্রথম অধ্যায়', 'দ্বিতীয় অধ্যায়', 'তৃতীয় অধ্যায়', 'চতুর্থ অধ্যায়', 'পঞ্চম অধ্যায়', 'ষষ্ঠ অধ্যায়', 'সপ্তম অধ্যায়', 'অষ্টম অধ্যায়', 'নবম অধ্যায়']
                chapters = {}
                for p in filtered_problems:
                    key = f"{p.get('chapter', 'অন্যান্য')} — {p.get('chapter_title', '')}".strip(' —')
                    chapters.setdefault(key, []).append(p)
                sorted_chapters = {}
                for ch_name in chapters_order:
                    for key in chapters:
                        if key.startswith(ch_name):
                            sorted_chapters[key] = chapters[key]
                return render_template('ppr.html', ppr=ppr_data, problems=filtered_problems, chapters=sorted_chapters, problems_count=len(filtered_problems), chapters_count=len(sorted_chapters), search_query=query)
            
            # অন্যথায় ওই অধ্যায়ের ভেতর কীওয়ার্ড সার্চ করবে
            problems = filtered_problems

        # =========================================================
        # সাধারণ সার্চ স্কোরিং
        # =========================================================
        query_norm = normalize_for_search(query)
        words = query_norm.split()
        results = []

        for p in problems:
            searchable = ' '.join([
                str(p.get('problem', '')), str(p.get('solution', '')), str(p.get('rule', '')),
                str(p.get('sub_rule', '')), str(p.get('rule_title', '')), str(p.get('chapter', '')),
                str(p.get('chapter_title', '')), ' '.join(p.get('keywords', []))
            ])
            body_score = calculate_relevance_score(searchable, words, query)
            title_score = calculate_title_score(p.get('problem', ''), words, query)
            total_score = body_score + title_score

            if query_norm in str(p.get('rule', '')).lower(): total_score += 500
            if query_norm in str(p.get('sub_rule', '')).lower(): total_score += 500

            if total_score > 0:
                p_copy = dict(p)
                p_copy['_score'] = total_score
                results.append(p_copy)

        results.sort(key=lambda x: x.get('_score', 0), reverse=True)
        if results:
            max_score = results[0].get('_score', 0)
            min_threshold = max_score * 0.15
            results = [r for r in results if r.get('_score', 0) >= min_threshold][:100]

        chapters_order = [
            'প্রথম অধ্যায়', 'দ্বিতীয় অধ্যায়', 'তৃতীয় অধ্যায়', 'চতুর্থ অধ্যায়', 'পঞ্চম অধ্যায়',
            'ষষ্ঠ অধ্যায়', 'সপ্তম অধ্যায়', 'অষ্টম অধ্যায়', 'নবম অধ্যায়'
        ]

        chapters = {}
        for p in results:
            key = f"{p.get('chapter', 'অন্যান্য')} — {p.get('chapter_title', '')}".strip(' —')
            chapters.setdefault(key, []).append(p)

        sorted_chapters = {}
        for ch_name in chapters_order:
            for key in chapters:
                if key.startswith(ch_name):
                    sorted_chapters[key] = chapters[key]
        for key in chapters:
            if key not in sorted_chapters:
                sorted_chapters[key] = chapters[key]

        return render_template('ppr.html', ppr=ppr_data, problems=results, chapters=sorted_chapters, problems_count=len(results), chapters_count=len(sorted_chapters), search_query=query)

    @app.route('/ppr/pdf')
    def ppr_pdf_viewer():
        page = request.args.get('page', 1, type=int)
        ppr_data = load_json(app.config['PPR_FILE'])
        return render_template('ppr_pdf_viewer.html', ppr=ppr_data, pdf_file=app.config['PPR_PDF'], current_page=page)

    @app.route('/pdf/<path:filename>')
    def serve_pdf(filename):
        pdf_dir = Path(app.config['STATIC_DIR']) / 'pdfs'
        safe_name = Path(filename).name
        try:
            return send_from_directory(pdf_dir, safe_name)
        except FileNotFoundError:
            flash('📄 PDF ফাইল পাওয়া যায়নি', 'error')
            return redirect(url_for('index'))

    # ==================== 🔐 Login / Logout ====================
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            password = request.form.get('password', '')
            if password == app.config['ADMIN_PASSWORD']:
                session['is_admin'] = True
                session.permanent = True
                flash('✅ সফলভাবে লগইন হয়েছে', 'success')
                next_url = request.args.get('next')
                if next_url and next_url.startswith('/'):
                    return redirect(next_url)
                return redirect(url_for('index'))
            else:
                flash('❌ ভুল পাসওয়ার্ড!', 'error')
        return render_template('login.html')

    @app.route('/logout')
    def logout():
        session.pop('is_admin', None)
        flash('👋 সফলভাবে লগআউট হয়েছে', 'success')
        return redirect(url_for('index'))

    app.logger.info(f"✅ সব routes register হয়েছে")