"""Strategy department.

Combines the research report and marketing plan into a StrategyPlan: which
topics to prioritize, how many posts per week, and rough KPI targets. This
is what the secretary department hands to the draft stage.
"""

from __future__ import annotations

from . import affiliate, config, draft, storage
from .models import MarketingPlan, ResearchReport, StrategyPlan, now_iso

AGENT_NAME = "カイ"  # 戦略部門担当

_WEEKDAY_ORDER = ["月", "火", "水", "木", "金", "土", "日"]


def _avg_engagement(report: ResearchReport) -> float:
    if not report.top_posts:
        return 0.0
    scores = [
        post.get("likes", 0) + post.get("replies", 0) * 2 + post.get("reposts", 0) * 3
        for post in report.top_posts
    ]
    return sum(scores) / len(scores)


def _pick_content_pillars(report: ResearchReport, top_n: int = 5) -> list[str]:
    # Hashtags are curated by the poster, so they make cleaner topic labels
    # than the free-text keyword tokenizer, which -- absent a Japanese
    # morphological analyzer -- turns unspaced Japanese sentences into a few
    # coarse multi-word chunks rather than real keywords (see research.py).
    # Exclude hashtags that coincide with a post_type label seen in this
    # report's own data (e.g. a "#解決法" hashtag) -- those describe the
    # post's *format*, not a topic, and would otherwise show up as a
    # confusing "topic: 解決法" slot in カイ's calendar.
    format_labels = set(report.patterns_by_type) | set(report.text_only_patterns_by_type)
    hashtag_topics = [h for h, _ in report.top_hashtags if h not in format_labels]
    if hashtag_topics:
        return hashtag_topics[:top_n]
    if report.top_hashtags:
        return [h for h, _ in report.top_hashtags[:top_n]]
    if report.top_keywords:
        return [kw for kw, _ in report.top_keywords[:top_n]]
    return ["ブランド紹介"]


def build_weekly_calendar(
    report: ResearchReport,
    marketing_plan: MarketingPlan,
    content_pillars: list[str],
    posts_per_day: int = 6,
    min_price_jpy: int | None = None,
    max_price_jpy: int | None = None,
) -> list[dict]:
    """カイ's day x hour content calendar.

    Slots are seeded from アヤ's day_hour_performance (best weekday x hour
    buckets among text-only posts); when a day doesn't have enough
    historical slots to fill posts_per_day, it's padded from
    report.best_hours_utc. post_type alternates between ハル's predicted
    trending type and the audience-resonant type so both growth and
    engagement are represented across the week. When the slot's topic
    matches a pain point in affiliate.PRODUCT_CATALOG and its price falls
    in [min_price_jpy, max_price_jpy], the slot carries a product NAME
    only -- never a URL; the actual link lives with レン (finance)/
    affiliate.py, not in the calendar or the post text.
    """
    slots_by_weekday: dict[str, list[tuple[int, float]]] = {}
    for weekday, hour, avg_score, _count in report.day_hour_performance:
        slots_by_weekday.setdefault(weekday, []).append((hour, avg_score))

    fallback_hours = [h for h, _ in report.best_hours_utc] or [9, 12, 18, 21, 0, 6]

    trend_types = [
        t for t in (marketing_plan.predicted_trending_type, marketing_plan.target_resonant_type) if t
    ] or ["解決法"]

    pillars = content_pillars or ["ブランド紹介"]

    calendar: list[dict] = []
    topic_i = 0
    for weekday in _WEEKDAY_ORDER:
        day_hours = sorted(slots_by_weekday.get(weekday, []), key=lambda item: item[1], reverse=True)
        hours_for_day = [hour for hour, _score in day_hours[:posts_per_day]]

        # Prefer distinct fallback hours first; once those run out (a small
        # sample dataset may only have a handful of best_hours_utc entries),
        # repeat them rather than under-filling the day -- posts_per_day is
        # an explicit target (e.g. "6 posts/day") that has to be met even
        # when the historical hour pool is thin.
        pad_i = 0
        while len(hours_for_day) < posts_per_day and pad_i < 200:
            candidate = fallback_hours[pad_i % len(fallback_hours)]
            if candidate not in hours_for_day or pad_i >= len(fallback_hours):
                hours_for_day.append(candidate)
            pad_i += 1
        hours_for_day = hours_for_day[:posts_per_day]

        for hour in hours_for_day:
            post_type = trend_types[topic_i % len(trend_types)]
            topic = pillars[topic_i % len(pillars)]
            topic_i += 1

            product = affiliate.recommend_in_price_range(topic, min_price_jpy, max_price_jpy)

            score_for_hour = next((s for h, s in day_hours if h == hour), None)
            basis = (
                f"過去実績(平均エンゲージメント{score_for_hour})に基づく実績枠"
                if score_for_hour is not None
                else "実績データ不足のため反応が良い時間帯(best_hours_utc)から補完"
            )
            if post_type == marketing_plan.predicted_trending_type:
                type_reason = "ハル予測: 伸びる型"
            elif post_type == marketing_plan.target_resonant_type:
                type_reason = "ハル予測: ターゲット層に刺さる型"
            else:
                type_reason = "型未予測のため既定"

            note_bits = [f"型: {post_type}({type_reason})", basis]
            if product:
                note_bits.append(f"商品: {product['name']}({product['price_jpy']}円、価格帯内)")
            elif post_type == "解決法":
                note_bits.append("該当価格帯の商品なし(商品提案は見送り)")

            calendar.append(
                {
                    "day": weekday,
                    "hour": hour,
                    "post_type": post_type,
                    "topic": topic,
                    "product_name": product["name"] if product else None,
                    "notes": " / ".join(note_bits),
                }
            )

    return calendar


# Phrasing below is calibrated against the operator's own real Threads
# account (162 text-only posts fetched via the Threads API and reviewed
# directly) rather than invented from scratch -- per operator direction,
# every future post must read like *that* account, not like generic
# affiliate copy. Recurring, reproducible traits observed in the real
# posts: short lines with frequent \n breaks (never a wall of text),
# casual sentence endings (だよ/だよね/ぅー/〜な、no である/します), a
# rhetorical question or shared-struggle opener that puts the reader and
# the writer on the same side ("私だけじゃないよね?", "わかる人にしか
# わからない"), and a closing line that invites rather than instructs --
# never "したほうがいい" (you should), always "してみてほしいな" / a
# question back to the reader. No lecturing tone, no polite/formal です・
# ます markers (secretary.qa_check_thread would flag mixing those in
# anyway), and a light single emoji at the very end of the closing line,
# matching how the real account punctuates a thought rather than
# decorating it.
_HOOK_TEMPLATES = [
    "「{pain}」\n\nこれ、わかる人にしか\nわからない辛さだと思う。",
    "「{pain}」って、\n地味にじわじわくるやつ。",
    "「{pain}」\n\n共感しかない…って人、\n地味に多い気がする。",
    "「{pain}」で悩んでるの、\n私だけじゃないよね?",
]

_TESTIMONIAL_TEMPLATES = [
    "うちも毎日そんな感じで、\n心も体もヘトヘトだった時期があって。\n\n特効薬なんてないと思ってたんだけど、\nあるものを試してから変わったんだよね。",
    "私も正直、心が折れかけてた。\n\n「これはもう仕方ない」って\n諦めかけてたんだけど、\nふと試してみたことがあって。",
    "毎日それでクタクタで、\n誰に聞いても\n「そのうち楽になるよ」しか言われなくて。\n\nでも、たまたま知ったことがきっかけで\n変わったんだよね。",
    "同じ悩みの人、周りにも結構いた。\n\nみんな我慢するしかないと\n思ってたけど、\n実はそうでもなかったんだよね。",
]


# 2-segment あるある->解決法 thread, restructured per operator direction:
#   投稿1 = 冒頭フック(1-2行) + あるある(1-2行) + 2投稿目に誘う一言
#   投稿2 = 解決法を詳しく + その後商品名
# Same real-account voice as _HOOK_TEMPLATES (soft/friendly/friend-to-friend,
# no である/ます, short \n-broken lines). variant_index picks one phrasing
# from each pool together so a batch doesn't repeat.
_HOOK_LINES = [
    "「{pain}」",
    "{pain}",
    "「{pain}」って、\nない?",
    "{pain}\n\nってこと、ない?",
]

_ARARU_LINES = [
    "これ、育児あるあるだと思う。\nわかる人にしかわからない辛さ。",
    "これもう、あるあるすぎない?",
    "育児してたら絶対通る道だよね。",
    "地味にしんどいやつ。\n育児あるある選手権あったら絶対入賞してると思う。",
]

_INVITE_LINES = [
    "実はこれ、ちゃんと解決できたから\n次の投稿で紹介するね🙏",
    "この悩み、あっさり解決したから\n続きは次の投稿で話すね",
    "諦めかけてたけど、\n解決法は次の投稿にまとめたよ",
    "どうやって乗り越えたか、\n2投稿目に書いたから見てね",
]

_SOLUTION_INTROS = [
    "実際にやってみたのはこれ。",
    "私が試して効果があったのはこれ。",
    "色々試した中で、一番効いたのがこれ。",
    "同じ悩みの人に共有したいんだけど、",
]


def build_araru_resolution_thread(product: dict, variant_index: int = 0) -> list[str]:
    """カイ's 2-segment あるある(relatable situation) -> 解決法(solution) thread.

    投稿1: 冒頭フック(1-2行) + あるある(1-2行) + 2投稿目に誘う一言。
    投稿2: 解決法を詳しく(前置き+resolution+一言) + その後[商品名]。

    Same real-account tone as build_product_thread (see the comment above
    _HOOK_TEMPLATES), same [商品名] bracket convention for the product.
    """
    insight = product.get("review_insight") or {}
    pain = insight.get("pain")
    resolution = insight.get("resolution")
    if not pain or not resolution:
        return []

    hook = _HOOK_LINES[variant_index % len(_HOOK_LINES)].format(pain=pain)
    araru = _ARARU_LINES[variant_index % len(_ARARU_LINES)]
    invite = _INVITE_LINES[variant_index % len(_INVITE_LINES)]
    post1 = f"{hook}\n\n{araru}\n\n{invite}"

    intro = _SOLUTION_INTROS[variant_index % len(_SOLUTION_INTROS)]
    post2 = (
        f"{intro}\n\n{resolution}。\n\n"
        "それからは気持ちがだいぶ楽になったよ。\n\n"
        f"使ったのは[{product['name']}]。\n\n"
        "同じように悩んでる人がいたら、\n無理しすぎずに一度試してみてほしいな🙏"
    )
    return [draft.truncate_to_limit(segment, config.THREADS_MAX_CHARS) for segment in (post1, post2)]


def build_araru_resolution_threads(products: list[dict]) -> list[dict]:
    """Batch version of build_araru_resolution_thread, grouped/tagged by genre (pain_point).

    Same contract as build_product_threads: products need review_insight
    already attached, products with no usable insight are skipped, and
    each product gets a different variant_index for phrasing variety.
    """
    threads = []
    for variant_index, product in enumerate(products):
        segments = build_araru_resolution_thread(product, variant_index=variant_index)
        if not segments:
            continue
        threads.append(
            {
                "genre": product.get("pain_point", "その他"),
                "product_name": product["name"],
                "price_jpy": product["price_jpy"],
                "review_count": product.get("review_count", 0),
                "segments": segments,
            }
        )
    return threads


def build_product_thread(product: dict, variant_index: int = 0) -> list[str]:
    """カイ's フック(hook) -> 体験談(testimonial) -> 解決法(solution) thread for one product.

    `product` must have ハル's `review_insight` attached (see
    marketing.analyze_products) with "pain"/"resolution" keys; products
    without a usable insight return an empty list (nothing to build from).
    Tone is friend-to-friend throughout, per operator direction -- no
    lecturing, no "you should," just "this is what worked for me," in the
    same voice as the operator's own real account (see the module-level
    comment above _HOOK_TEMPLATES). The product name is embedded as
    [商品名] (never a URL) in the final segment; draft.visible_length
    excludes it from the 500-char budget, consistent with how the rest of
    the pipeline treats bracketed tags.

    variant_index cycles through a small pool of hook/testimonial phrasings
    so a batch of threads (see build_product_threads) doesn't read as the
    same post copy-pasted with the noun swapped out.
    """
    insight = product.get("review_insight") or {}
    pain = insight.get("pain")
    resolution = insight.get("resolution")
    if not pain or not resolution:
        return []

    hook = _HOOK_TEMPLATES[variant_index % len(_HOOK_TEMPLATES)].format(pain=pain)
    testimonial = _TESTIMONIAL_TEMPLATES[variant_index % len(_TESTIMONIAL_TEMPLATES)]
    solution = (
        f"{resolution}。\n\n"
        f"使ったのは[{product['name']}]。\n\n"
        "同じように悩んでる人がいたら、\n無理しすぎずに一度試してみてほしいな🙏"
    )
    return [draft.truncate_to_limit(segment, config.THREADS_MAX_CHARS) for segment in (hook, testimonial, solution)]


def build_product_threads(products: list[dict]) -> list[dict]:
    """Batch version of build_product_thread, grouped/tagged by genre (pain_point).

    `products` should already carry ハル's review_insight (see
    marketing.analyze_products) and レン's price filtering (see
    affiliate.products_in_price_range) -- this function doesn't re-check
    price, it just builds the thread copy. Products with no usable review
    insight are skipped rather than shipping an empty thread. Each product
    gets a different variant_index so hook/testimonial phrasing varies
    across the batch.
    """
    threads = []
    for variant_index, product in enumerate(products):
        segments = build_product_thread(product, variant_index=variant_index)
        if not segments:
            continue
        threads.append(
            {
                "genre": product.get("pain_point", "その他"),
                "product_name": product["name"],
                "price_jpy": product["price_jpy"],
                "review_count": product.get("review_count", 0),
                "segments": segments,
            }
        )
    return threads


def build_strategy_plan(report: ResearchReport, marketing_plan: MarketingPlan) -> StrategyPlan:
    content_pillars = _pick_content_pillars(report)
    priority_topics = content_pillars[:3]

    kpi_targets = {
        "weekly_posts": marketing_plan.posting_cadence_per_week,
        "target_avg_engagement": round(_avg_engagement(report) * 1.1, 1),
        "target_follower_growth_pct": 5.0,
    }

    notes = (
        f"上位キーワード({', '.join(content_pillars)})を軸に、"
        f"週{marketing_plan.posting_cadence_per_week}件を目安に投稿する。"
    )

    posts_per_day = max(1, round(marketing_plan.posting_cadence_per_week / 7))
    weekly_calendar = build_weekly_calendar(
        report,
        marketing_plan,
        content_pillars,
        posts_per_day=posts_per_day,
        min_price_jpy=config.AFFILIATE_MIN_PRICE_JPY,
        max_price_jpy=config.AFFILIATE_MAX_PRICE_JPY,
    )

    return StrategyPlan(
        id=storage.new_id("strategy"),
        generated_at=now_iso(),
        source_report=report.id,
        source_marketing_plan=marketing_plan.id,
        content_pillars=content_pillars,
        priority_topics=priority_topics,
        weekly_post_target=marketing_plan.posting_cadence_per_week,
        kpi_targets=kpi_targets,
        notes=notes,
        weekly_calendar=weekly_calendar,
    )


def save_strategy_plan(plan: StrategyPlan, strategy_dir=None) -> str:
    strategy_dir = strategy_dir or config.STRATEGY_DIR
    path = strategy_dir / f"{plan.id}.json"
    storage.write_json(path, plan.to_dict())
    return str(path)


def latest_strategy_plan(strategy_dir=None) -> StrategyPlan | None:
    strategy_dir = strategy_dir or config.STRATEGY_DIR
    files = storage.list_json_files(strategy_dir)
    if not files:
        return None
    latest = max(files, key=lambda p: p.stat().st_mtime)
    return StrategyPlan.from_dict(storage.read_json(latest))


def run_strategy(
    report: ResearchReport, marketing_plan: MarketingPlan, strategy_dir=None
) -> tuple[StrategyPlan, str]:
    plan = build_strategy_plan(report, marketing_plan)
    path = save_strategy_plan(plan, strategy_dir)
    return plan, path
