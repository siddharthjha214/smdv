/* ============================================================
   SMDV Tracker — app.js
   Handles: theme, nav (desktop + mobile), data fetch, render
   ============================================================ */

const GOOGLE_SCRIPT_URL =
    "https://script.google.com/macros/s/AKfycbyAarmgcJWsMYdHW9fhbKrTZXGsu77TFKVAQanMZmTY1xdgtq320MgiZfusuLvXlpAF/exec";

let activeVideosData  = [];
let deletedVideosData = [];
let currentTab        = "active"; // "active" | "deleted"

/* ── Boot ─────────────────────────────────────────────────── */
document.addEventListener("DOMContentLoaded", () => {
    setupThemeToggle();
    setupNavigation();
    setupMobileMenu();
    fetchData();
});

/* ── Theme Toggle ─────────────────────────────────────────── */
function setupThemeToggle() {
    const btn   = document.getElementById("theme-toggle");
    const icon  = document.getElementById("theme-icon");
    const html  = document.documentElement;

    const saved = localStorage.getItem("theme");
    if (saved === "light") {
        html.setAttribute("data-theme", "light");
        icon.className = "bx bx-moon";
    }

    btn.addEventListener("click", () => {
        const isDark = html.getAttribute("data-theme") === "dark";
        html.setAttribute("data-theme", isDark ? "light" : "dark");
        icon.className = isDark ? "bx bx-moon" : "bx bx-sun";
        localStorage.setItem("theme", isDark ? "light" : "dark");
    });
}

/* ── Desktop Navigation ───────────────────────────────────── */
function setupNavigation() {
    const navVideos  = document.getElementById("nav-videos");
    const navContact = document.getElementById("nav-contact");
    const secVideos  = document.getElementById("section-videos");
    const secContact = document.getElementById("section-contact");

    function showSection(show, hide, activeBtn, inactiveBtn) {
        show.classList.add("active");
        hide.classList.remove("active");
        activeBtn.classList.add("active");
        activeBtn.setAttribute("aria-current", "page");
        inactiveBtn.classList.remove("active");
        inactiveBtn.removeAttribute("aria-current");

        // Mirror state to mobile menu buttons
        const mobVideos  = document.getElementById("mob-nav-videos");
        const mobContact = document.getElementById("mob-nav-contact");
        if (activeBtn === navVideos) {
            mobVideos.classList.add("active");
            mobContact.classList.remove("active");
        } else {
            mobContact.classList.add("active");
            mobVideos.classList.remove("active");
        }

        closeMobileMenu();
        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    navVideos.addEventListener("click",  () => showSection(secVideos, secContact, navVideos, navContact));
    navContact.addEventListener("click", () => showSection(secContact, secVideos, navContact, navVideos));

    // Mobile nav mirrors
    document.getElementById("mob-nav-videos").addEventListener("click",
        () => showSection(secVideos, secContact, navVideos, navContact));
    document.getElementById("mob-nav-contact").addEventListener("click",
        () => showSection(secContact, secVideos, navContact, navVideos));

    // Logo home
    document.getElementById("logo-home").addEventListener("click", (e) => {
        e.preventDefault();
        showSection(secVideos, secContact, navVideos, navContact);
    });

    /* ── Video sub-tabs ── */
    const tabActive  = document.getElementById("tab-active");
    const tabDeleted = document.getElementById("tab-deleted");

    tabActive.addEventListener("click", () => {
        tabActive.classList.add("active");
        tabActive.setAttribute("aria-selected", "true");
        tabDeleted.classList.remove("active");
        tabDeleted.setAttribute("aria-selected", "false");
        currentTab = "active";
        renderGrid();
    });

    tabDeleted.addEventListener("click", () => {
        tabDeleted.classList.add("active");
        tabDeleted.setAttribute("aria-selected", "true");
        tabActive.classList.remove("active");
        tabActive.setAttribute("aria-selected", "false");
        currentTab = "deleted";
        renderGrid();
    });

    /* ── Modal close ── */
    document.getElementById("close-modal-btn").addEventListener("click", closeModal);
    document.getElementById("video-modal").addEventListener("click", (e) => {
        if (e.target.id === "video-modal") closeModal();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") closeModal();
    });
}

/* ── Mobile Menu ──────────────────────────────────────────── */
function setupMobileMenu() {
    const hamburger = document.getElementById("hamburger");
    const menu      = document.getElementById("mobile-menu");

    hamburger.addEventListener("click", () => {
        const isOpen = menu.classList.toggle("open");
        hamburger.classList.toggle("open", isOpen);
        hamburger.setAttribute("aria-expanded", String(isOpen));
    });
}

function closeMobileMenu() {
    const hamburger = document.getElementById("hamburger");
    const menu      = document.getElementById("mobile-menu");
    menu.classList.remove("open");
    hamburger.classList.remove("open");
    hamburger.setAttribute("aria-expanded", "false");
}

/* ── Fetch Data ───────────────────────────────────────────── */
async function fetchData() {
    const loading = document.getElementById("loading");
    const grid    = document.getElementById("video-grid");

    loading.style.display = "flex";
    grid.innerHTML = "";

    try {
        const [activeRes, deletedRes] = await Promise.all([
            fetch(`${GOOGLE_SCRIPT_URL}?action=get_active_videos`),
            fetch(`${GOOGLE_SCRIPT_URL}?action=get_deleted_videos`)
        ]);

        const activeMap   = await activeRes.json();
        deletedVideosData = await deletedRes.json();

        // Convert active map → sorted array
        activeVideosData = Object.entries(activeMap)
            .map(([id, data]) => ({ ...data, video_id: id }))
            .sort((a, b) => {
                // Newest first; Unknown dates go to the bottom
                const da = new Date(String(a.upload_time).replace(' IST',''));
                const db = new Date(String(b.upload_time).replace(' IST',''));
                const va = isNaN(da) ? 0 : da.getTime();
                const vb = isNaN(db) ? 0 : db.getTime();
                return vb - va;
            });

        // Sort deleted newest first
        deletedVideosData.sort((a, b) =>
            new Date(b.deleted_time) - new Date(a.deleted_time));

        loading.style.display = "none";
        renderStats();
        renderGrid();

    } catch (err) {
        console.error("Fetch error:", err);
        loading.innerHTML =
            `<p style="color:var(--danger);font-size:.9rem;">
                <i class='bx bx-error-circle' style="font-size:2rem;display:block;margin-bottom:.5rem;"></i>
                Failed to sync. Please refresh and try again.
             </p>`;
    }
}

/* ── Stats Bar ────────────────────────────────────────────── */
function renderStats() {
    const el = document.getElementById("stats-overview");
    el.innerHTML = `
        <div class="stat-item">
            <i class='bx bx-video'></i>
            <strong>${activeVideosData.length}</strong> Active
        </div>
        <div class="stat-item">
            <i class='bx bx-trash'></i>
            <strong>${deletedVideosData.length}</strong> Deleted
        </div>
        <div class="stat-item">
            <i class='bx bx-time'></i>
            Updated&nbsp;<strong>just now</strong>
        </div>
    `;
}

/* ── Format Date ──────────────────────────────────────────── */
// Dates are already stored as formatted strings like:
//   "27 May 2026 11:30 PM IST"  (active upload_time)
//   "27 May 2026 11:35 PM IST"  (deleted_time / original_upload_time)
// We simply return them, trimming " IST" for compact card display.
function formatDate(dateStr, compact) {
    if (!dateStr || dateStr === "Unknown" || dateStr === "") return "—";
    const s = String(dateStr).trim();
    if (compact) {
        // Remove " IST" and time portion for card display → "27 May 2026"
        return s.replace(/ IST$/i, "").replace(/\s+\d{1,2}:\d{2}\s*(AM|PM)?$/i, "").trim();
    }
    return s; // Full string for modal
}

/* ── Render Grid ──────────────────────────────────────────── */
function renderGrid() {
    const grid = document.getElementById("video-grid");
    grid.innerHTML = "";

    let data = currentTab === "active" ? activeVideosData : deletedVideosData;

    // ── Monitoring-since notice (deleted tab only) ──
    if (currentTab === "deleted") {
        const notice = document.createElement("div");
        notice.className = "monitoring-notice";
        notice.setAttribute("role", "note");
        notice.innerHTML = `
            <i class='bx bx-calendar-check' aria-hidden="true"></i>
            <span>This tracker has been monitoring Sandeep Maheshwari's channel since <strong>May 2026</strong>. Only deletions detected from that date onwards are listed here.</span>
        `;
        grid.appendChild(notice);
    }

    if (!data.length) {
        grid.innerHTML += `
            <p style="color:var(--text-muted);grid-column:1/-1;text-align:center;padding:4rem 0;font-size:.95rem;">
                No videos found.
            </p>`;
        return;
    }

    // ── Render ALL cards; hide overflow (index ≥ 12) by default ──
    const VISIBLE_LIMIT = 12;
    const hasOverflow   = currentTab === "active" && data.length > VISIBLE_LIMIT;

    data.forEach((video, index) => {
        const card = document.createElement("div");
        card.className = "card";
        card.setAttribute("role", "article");

        // Tag & hide cards beyond the default limit
        if (hasOverflow && index >= VISIBLE_LIMIT) {
            card.dataset.overflow = "true";
            card.style.display = "none";
        }

        if (currentTab === "active") {
            /* ── Active Video Card ── */
            // Use hqdefault as primary — it ALWAYS returns a real thumbnail.
            // maxresdefault silently returns a tiny grey image (200 OK) for older videos,
            // so onerror never fires for it — making it useless as a src.
            const thumbUrl = `https://img.youtube.com/vi/${video.video_id}/hqdefault.jpg`;
            const dateStr  = formatDate(video.upload_time, true);

            card.innerHTML = `
                <div class="thumbnail-container">
                    <img src="${thumbUrl}"
                         alt="${escapeHtml(video.title)} thumbnail"
                         loading="lazy"
                         data-videoid="${video.video_id}"
                         onerror="thumbFallback(this,'${video.video_id}','active')">
                    <div class="play-overlay" aria-hidden="true">
                        <div class="play-btn"><i class='bx bx-play'></i></div>
                    </div>
                </div>
                <div class="card-content">
                    <h3 class="card-title">${escapeHtml(video.title)}</h3>
                    <div class="card-meta">
                        <span class="card-date">
                            <i class='bx bx-calendar-alt'></i>${dateStr}
                        </span>
                    </div>
                </div>
            `;

            card.addEventListener("click", () => window.open(video.url, "_blank"));
            card.setAttribute("tabindex", "0");
            card.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") window.open(video.url, "_blank");
            });

        } else {
            /* ── Deleted Video Card ── */
            const backupId = video.backup_video_id || "";
            // hqdefault is always a real thumbnail; fall back to placeholder if no backup
            const thumbUrl = backupId
                ? `https://img.youtube.com/vi/${backupId}/hqdefault.jpg`
                : `https://placehold.co/640x360/1a0010/ff4f6a?text=No+Backup`;
            const fallbackId = backupId || video.video_id;
            const dateStr  = formatDate(video.original_upload_time, true);

            card.innerHTML = `
                <div class="thumbnail-container">
                    <img src="${thumbUrl}"
                         alt="${escapeHtml(video.title)} thumbnail"
                         loading="lazy"
                         onerror="thumbFallback(this,'${fallbackId}','deleted')">
                    <div class="play-overlay" aria-hidden="true">
                        <div class="play-btn" style="background:var(--danger);">
                            <i class='bx bx-info-circle'></i>
                        </div>
                    </div>
                </div>
                <div class="card-content">
                    <h3 class="card-title">${escapeHtml(video.title)}</h3>
                    <div class="card-meta">
                        <span class="card-date">
                            <i class='bx bx-calendar-alt'></i>${dateStr}
                        </span>
                        <span class="badge deleted">
                            <i class='bx bx-trash'></i> Deleted
                        </span>
                    </div>
                </div>
            `;

            card.addEventListener("click", () => openModal(video));
            card.setAttribute("tabindex", "0");
            card.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") openModal(video);
            });
        }

        grid.appendChild(card);
    });

    /* ── View More Button (shown only when no search is active) ── */
    if (hasOverflow) {
        const wrap = document.createElement("div");
        wrap.className = "view-more-wrap";
        wrap.id = "view-more-wrap";
        wrap.innerHTML = `
            <a href="https://www.youtube.com/@SandeepSeminars/videos"
               target="_blank"
               rel="noopener noreferrer"
               class="btn-view-more">
                <i class='bx bxl-youtube'></i>
                View More on YouTube
            </a>
        `;
        grid.appendChild(wrap);
    }
}

/* ── Modal ────────────────────────────────────────────────── */
function openModal(video) {
    const modal     = document.getElementById("video-modal");
    const modalBody = document.getElementById("modal-body");

    const uploadDate = formatDate(video.original_upload_time, false);
    const deleteDate = formatDate(video.deleted_time, false);

    let backupSection = "";
    if (video.backup_video_id) {
        backupSection = `
            <a href="https://youtube.com/watch?v=${video.backup_video_id}"
               target="_blank"
               rel="noopener noreferrer"
               class="btn-watch">
                <i class='bx bx-play-circle'></i> Watch Backup Video
            </a>`;
    } else {
        backupSection = `
            <p style="color:var(--danger);margin-top:.75rem;font-size:.875rem;text-align:center;">
                <i class='bx bx-error-circle'></i> No backup available for this video.
            </p>`;
    }

    modalBody.innerHTML = `
        <div class="modal-body-content">
            <h2 id="modal-title">${escapeHtml(video.title)}</h2>
            <div class="detail-row">
                <span>Original Upload</span>
                <span>${escapeHtml(uploadDate)}</span>
            </div>
            <div class="detail-row">
                <span>Deleted At</span>
                <span>${escapeHtml(deleteDate)}</span>
            </div>
            <div class="detail-row">
                <span>Status</span>
                <span style="color:var(--danger);font-weight:700;">
                    <i class='bx bx-trash'></i> Deleted / Private
                </span>
            </div>
            ${backupSection}
        </div>
    `;

    modal.classList.add("active");
    document.body.style.overflow = "hidden";

    // Focus close button for accessibility
    setTimeout(() => {
        document.getElementById("close-modal-btn").focus();
    }, 100);
}

function closeModal() {
    const modal = document.getElementById("video-modal");
    modal.classList.remove("active");
    document.body.style.overflow = "";
}

/* ── Helpers ──────────────────────────────────────────────── */
function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g,  "&amp;")
        .replace(/</g,  "&lt;")
        .replace(/>/g,  "&gt;")
        .replace(/"/g,  "&quot;")
        .replace(/'/g,  "&#039;");
}

/**
 * Thumbnail error cascade.
 * We now use hqdefault.jpg as the PRIMARY src (always a real image).
 * If even that fails (network error etc.), we try lower qualities then placeholder.
 */
function thumbFallback(img, videoId, type) {
    const placeholder = type === "deleted"
        ? "https://placehold.co/640x360/1a0010/ff4f6a?text=No+Backup"
        : "https://placehold.co/640x360/0f0f1e/6c63ff?text=SMDV";

    // hqdefault is already loaded as primary; try lower quality on error
    const fallbacks = [
        `https://img.youtube.com/vi/${videoId}/mqdefault.jpg`,
        `https://img.youtube.com/vi/${videoId}/sddefault.jpg`,
        `https://img.youtube.com/vi/${videoId}/default.jpg`,
        placeholder
    ];

    let idx = 0;
    img.onerror = function () {
        if (idx < fallbacks.length) {
            img.src = fallbacks[idx++];
        } else {
            img.onerror = null; // stop any loop
        }
    };
}

/* ── Live Search ──────────────────────────────────────────── */
function setupSearch() {
    const input     = document.getElementById("search-input");
    const clearBtn  = document.getElementById("search-clear");
    if (!input) return;

    let debounceTimer;

    input.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const q = input.value.trim();
            clearBtn.style.display = q ? "flex" : "none";
            filterCards(q);
        }, 200);
    });

    clearBtn.addEventListener("click", () => {
        input.value = "";
        clearBtn.style.display = "none";
        filterCards("");
        input.focus();
    });

    // Reset search when tabs switch
    document.getElementById("tab-active").addEventListener("click",  () => resetSearch());
    document.getElementById("tab-deleted").addEventListener("click", () => resetSearch());
}

function resetSearch() {
    const input    = document.getElementById("search-input");
    const clearBtn = document.getElementById("search-clear");
    if (!input) return;
    input.value = "";
    clearBtn.style.display = "none";
}

function filterCards(query) {
    const grid      = document.getElementById("video-grid");
    const cards     = grid.querySelectorAll(".card");
    const viewMore  = document.getElementById("view-more-wrap");
    const q         = query.toLowerCase().trim();
    const isSearching = q.length > 0;

    let visibleCount = 0;

    cards.forEach(card => {
        const titleEl   = card.querySelector(".card-title");
        if (!titleEl) return;

        const isOverflow = card.dataset.overflow === "true";
        const matches    = !isSearching || titleEl.textContent.toLowerCase().includes(q);

        if (isSearching) {
            // Search mode: show ALL matching cards regardless of overflow
            card.style.display = matches ? "" : "none";
        } else {
            // Default mode: restore overflow cards to hidden, show the rest
            card.style.display = isOverflow ? "none" : "";
        }

        if (matches || !isSearching) {
            if (!isOverflow || isSearching) visibleCount++;
        }
    });

    // Show/hide the View More button — hide it while searching
    if (viewMore) {
        viewMore.style.display = isSearching ? "none" : "";
    }

    // Empty state message
    let emptyMsg = grid.querySelector(".search-empty");
    if (isSearching && visibleCount === 0) {
        if (!emptyMsg) {
            emptyMsg = document.createElement("p");
            emptyMsg.className = "search-empty";
            emptyMsg.style.cssText =
                "color:var(--text-muted);grid-column:1/-1;text-align:center;padding:4rem 0;font-size:.9rem;";
            grid.appendChild(emptyMsg);
        }
        emptyMsg.textContent = `No videos found for "${query}".`;
    } else if (emptyMsg) {
        emptyMsg.remove();
    }

    // Update result count hint in search box when actively searching
    const hint = document.getElementById("search-hint");
    if (hint) {
        hint.textContent = isSearching
            ? `${visibleCount} result${visibleCount !== 1 ? "s" : ""} found across all videos`
            : "";
    }
}

/* ── Scroll-to-Top ────────────────────────────────────────── */
function setupScrollTop() {
    const btn = document.getElementById("scroll-top");
    if (!btn) return;

    window.addEventListener("scroll", () => {
        btn.classList.toggle("visible", window.scrollY > 400);
    }, { passive: true });

    btn.addEventListener("click", () => {
        window.scrollTo({ top: 0, behavior: "smooth" });
    });
}

// Initialise new features after DOM is ready
document.addEventListener("DOMContentLoaded", () => {
    setupSearch();
    setupScrollTop();
});
