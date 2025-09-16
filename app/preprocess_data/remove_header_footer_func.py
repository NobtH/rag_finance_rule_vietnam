import re
from typing import List
from difflib import SequenceMatcher
import tqdm

# ======================
# UTIL: chuẩn hoá & so khớp
# ======================
def normalize_line(s: str) -> str:
    """Chuẩn hoá 1 dòng: strip + gộp khoảng trắng liên tiếp."""
    if s is None:
        return ""
    return re.sub(r"\s+", " ", s.strip())

def similar(a: str, b: str) -> float:
    """Tính độ tương đồng giữa 2 chuỗi (0..1)."""
    a = normalize_line(a)
    b = normalize_line(b)
    return SequenceMatcher(None, a, b).ratio()

def first_k_nonempty(lines: List[str], k: int) -> List[str]:
    """Lấy k dòng đầu KHÔNG TRỐNG (đã normalize)."""
    out = []
    for ln in lines:
        n = normalize_line(ln)
        if n:
            out.append(n)
            if len(out) == k:
                break
    return out

def last_k_nonempty(lines: List[str], k: int) -> List[str]:
    """Lấy k dòng cuối KHÔNG TRỐNG (đã normalize)."""
    out = []
    for ln in reversed(lines):
        n = normalize_line(ln)
        if n:
            out.append(n)
            if len(out) == k:
                break
    return list(reversed(out))

def squeeze_blank_lines(text: str) -> str:
    """Loại bỏ tất cả dòng trống hoàn toàn."""
    out_lines = []
    for ln in text.splitlines():
        if ln.strip():  # chỉ giữ dòng có nội dung
            out_lines.append(ln.rstrip())
    return "\n".join(out_lines).strip()

def find_repeated_lines(pages_lines: List[List[str]], from_top: bool,
                        max_check_lines: int, sim_threshold: float, min_ratio: float) -> List[str]:
    """
    Tìm các dòng lặp (header/footer) giữa các trang.
    from_top=True  -> header
    from_top=False -> footer
    """
    n_pages = len(pages_lines)
    repeated = []

    for offset in range(max_check_lines):
        pos_lines = []
        for lines in pages_lines:
            if from_top:
                if len(lines) > offset:
                    pos_lines.append(normalize_line(lines[offset]))
            else:
                if len(lines) > offset:
                    pos_lines.append(normalize_line(lines[-(offset+1)]))

        # bỏ qua nếu hầu hết rỗng
        pos_lines = [l for l in pos_lines if l]
        if not pos_lines:
            continue

        # chọn dòng phổ biến nhất
        best = ""
        best_support = 0
        for cand in pos_lines:
            support = sum(1 for x in pos_lines if similar(cand, x) >= sim_threshold)
            if support > best_support:
                best_support = support
                best = cand

        if best_support / n_pages >= min_ratio:
            repeated.append(best)

    return repeated

# ======================
# REMOVE FUNCTIONS
# ======================
def remove_repeated_footer(pages_text: List[str], max_check_lines: int = 5,
                           sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    pages_lines = [txt.splitlines() for txt in pages_text]
    common_foot = find_repeated_lines(pages_lines, from_top=False,
                                      max_check_lines=max_check_lines,
                                      sim_threshold=sim_threshold,
                                      min_ratio=min_ratio)

    cleaned_pages = []
    for lines in pages_lines:
        new_lines = lines[:]
        for cand in common_foot:
            # từ dưới lên
            for i in range(len(new_lines)-1, -1, -1):
                if similar(normalize_line(new_lines[i]), cand) >= sim_threshold:
                    new_lines.pop(i)
                    break
        cleaned_pages.append("\n".join(new_lines))

    return [squeeze_blank_lines(t) for t in cleaned_pages]


def remove_repeated_header(pages_text: List[str], max_check_lines: int = 5,
                           sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    pages_lines = [txt.splitlines() for txt in pages_text]
    common_head = find_repeated_lines(pages_lines, from_top=True,
                                      max_check_lines=max_check_lines,
                                      sim_threshold=sim_threshold,
                                      min_ratio=min_ratio)

    cleaned_pages = []
    for lines in pages_lines:
        new_lines = lines[:]
        for cand in common_head:
            # từ trên xuống
            for i in range(len(new_lines)):
                if similar(normalize_line(new_lines[i]), cand) >= sim_threshold:
                    new_lines.pop(i)
                    break
        cleaned_pages.append("\n".join(new_lines))

    return [squeeze_blank_lines(t) for t in cleaned_pages]


def remove_headers_and_footers(pages_text: List[str], max_check_lines: int = 10,
                                        sim_threshold: float = 0.8, min_ratio: float = 0.6) -> List[str]:
    cleaned = remove_repeated_header(pages_text, max_check_lines, sim_threshold, min_ratio)
    cleaned = remove_repeated_footer(cleaned, max_check_lines, sim_threshold, min_ratio)
    return cleaned

# ///////////////////////


def collect_candidates(pages_lines, k=10):
    """Thu thập k dòng đầu/cuối của mỗi trang làm ứng viên header/footer."""
    candidates = []
    for lines in pages_lines:
        head = first_k_nonempty(lines, k)
        foot = last_k_nonempty(lines, k)
        candidates.extend(head + foot)
    return candidates


def cluster_repeated(candidates, sim_threshold=0.8, min_ratio=0.6, n_pages=1):
    """Nhóm các dòng ứng viên lặp lại nhiều lần."""
    clusters = []
    used = set()
    # for i in candidates[:20]:
    #     print(i)

    for i, cand in enumerate(candidates):
        if i in used:
            continue
        group = [cand]
        used.add(i)
        for j, other in enumerate(candidates):
            if j in used:
                continue
            if similar(cand, other) >= sim_threshold:
                group.append(other)
                used.add(j)
        # chọn đại diện
        rep = max(group, key=len)
        support = len(group)
        if support / n_pages >= min_ratio:
            clusters.append(rep)
    return clusters


def remove_candidates_from_pages(pages_lines, reps, sim_threshold=0.8):
    """Xoá tất cả dòng trong toàn bộ trang tương tự với các reps."""
    cleaned_pages = []
    for lines in pages_lines:
        new_lines = []
        for ln in tqdm.tqdm(lines):
            if any(similar(normalize_line(ln), rep) >= sim_threshold for rep in reps):
                continue  # bỏ dòng lặp
            new_lines.append(ln)
        cleaned_pages.append("\n".join(new_lines))
    return [squeeze_blank_lines(t) for t in cleaned_pages]


def remove_headers_and_footers_v2(pages_text, num_pages, max_check_lines=10, sim_threshold=0.8, min_ratio=0.6):
    """Phiên bản mới: detect header/footer từ 10 dòng đầu/cuối, xoá toàn văn bản."""
    pages_lines = [txt.splitlines() for txt in pages_text]

    # B1: thu thập ứng viên
    candidates = collect_candidates(pages_lines, k=max_check_lines)

    # B2: tìm các dòng lặp
    reps = cluster_repeated(candidates,
                            sim_threshold=sim_threshold,
                            min_ratio=min_ratio,
                            n_pages=num_pages)
    print(">>> Header/Footer phát hiện:", reps)

    # B3: xoá trong toàn bộ text
    return remove_candidates_from_pages(pages_lines, reps, sim_threshold=sim_threshold)