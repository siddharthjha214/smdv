const GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbw81BtuAqr6NlISRUHgazF7_Q3rFXmELbmDtg5h0oKtZrU8ZWvBLstzlXqJJdKwzZUG/exec";

let activeVideosData = [];
let deletedVideosData = [];
let currentTab = 'active'; // 'active' or 'deleted'

document.addEventListener('DOMContentLoaded', () => {
    setupThemeToggle();
    setupNavigation();
    fetchData();
});

function setupThemeToggle() {
    const toggleBtn = document.getElementById('theme-toggle');
    const themeIcon = document.getElementById('theme-icon');
    const htmlEl = document.documentElement;

    // Check local storage
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'light') {
        htmlEl.setAttribute('data-theme', 'light');
        themeIcon.className = 'bx bx-moon';
    }

    toggleBtn.addEventListener('click', () => {
        if (htmlEl.getAttribute('data-theme') === 'dark') {
            htmlEl.setAttribute('data-theme', 'light');
            themeIcon.className = 'bx bx-moon';
            localStorage.setItem('theme', 'light');
        } else {
            htmlEl.setAttribute('data-theme', 'dark');
            themeIcon.className = 'bx bx-sun';
            localStorage.setItem('theme', 'dark');
        }
    });
}

function setupNavigation() {
    // Top Nav
    const navVideos = document.getElementById('nav-videos');
    const navContact = document.getElementById('nav-contact');
    const secVideos = document.getElementById('section-videos');
    const secContact = document.getElementById('section-contact');

    navVideos.addEventListener('click', () => {
        navVideos.classList.add('active');
        navContact.classList.remove('active');
        secVideos.classList.add('active');
        secContact.classList.remove('active');
    });

    navContact.addEventListener('click', () => {
        navContact.classList.add('active');
        navVideos.classList.remove('active');
        secContact.classList.add('active');
        secVideos.classList.remove('active');
    });

    // Sub Tabs (Active / Deleted)
    const tabActive = document.getElementById('tab-active');
    const tabDeleted = document.getElementById('tab-deleted');

    tabActive.addEventListener('click', () => {
        tabActive.classList.add('active');
        tabDeleted.classList.remove('active');
        currentTab = 'active';
        renderGrid();
    });

    tabDeleted.addEventListener('click', () => {
        tabDeleted.classList.add('active');
        tabActive.classList.remove('active');
        currentTab = 'deleted';
        renderGrid();
    });

    // Modal close
    document.querySelector('.close-modal').addEventListener('click', closeModal);
    document.getElementById('video-modal').addEventListener('click', (e) => {
        if (e.target.id === 'video-modal') closeModal();
    });
}

async function fetchData() {
    const loading = document.getElementById('loading');
    const grid = document.getElementById('video-grid');
    loading.style.display = 'flex';
    grid.innerHTML = '';

    try {
        // Fetch both concurrently
        const [activeRes, deletedRes] = await Promise.all([
            fetch(`${GOOGLE_SCRIPT_URL}?action=get_active_videos`),
            fetch(`${GOOGLE_SCRIPT_URL}?action=get_deleted_videos`)
        ]);

        const activeMap = await activeRes.json();
        deletedVideosData = await deletedRes.json();

        // Convert active map to sorted array and inject the video_id from the key
        activeVideosData = Object.entries(activeMap).map(([id, data]) => {
            return { ...data, video_id: id };
        }).sort((a, b) => {
            return new Date(b.upload_time) - new Date(a.upload_time);
        });

        // Sort deleted newest first
        deletedVideosData.sort((a, b) => new Date(b.deleted_time) - new Date(a.deleted_time));

        loading.style.display = 'none';
        renderGrid();

    } catch (error) {
        console.error("Error fetching data:", error);
        loading.innerHTML = '<p style="color: var(--danger)">Failed to sync with database. Please try again later.</p>';
    }
}

function renderGrid() {
    const grid = document.getElementById('video-grid');
    grid.innerHTML = '';

    let data = currentTab === 'active' ? activeVideosData : deletedVideosData;

    if (data.length === 0) {
        grid.innerHTML = `<p style="color: var(--text-muted); grid-column: 1/-1;">No videos found.</p>`;
        return;
    }

    let showMoreButton = false;
    if (currentTab === 'active' && data.length > 12) {
        data = data.slice(0, 12);
        showMoreButton = true;
    }

    data.forEach(video => {
        const card = document.createElement('div');
        card.className = 'card';

        let thumbnailUrl = '';
        let metaHtml = '';

        if (currentTab === 'active') {
            thumbnailUrl = `https://img.youtube.com/vi/${video.video_id}/hqdefault.jpg`;
            
            // Format time relative or simple date (we will just use the provided text for now)
            metaHtml = `
                <span>${video.upload_time.split(' ')[0]} ${video.upload_time.split(' ')[1]}</span>
            `;

            card.innerHTML = `
                <div class="thumbnail-container">
                    <img src="${thumbnailUrl}" alt="Thumbnail" loading="lazy" onerror="this.src='https://via.placeholder.com/640x360.png?text=No+Thumbnail'">
                    <div class="play-overlay">
                        <div class="play-btn"><i class='bx bx-play'></i></div>
                    </div>
                </div>
                <div class="card-content">
                    <h3 class="card-title">${video.title}</h3>
                    <div class="card-meta">
                        ${metaHtml}
                    </div>
                </div>
            `;

            // Open original video on click
            card.addEventListener('click', () => {
                window.open(video.url, '_blank');
            });

        } else {
            // Deleted video
            if (video.backup_video_id) {
                thumbnailUrl = `https://img.youtube.com/vi/${video.backup_video_id}/hqdefault.jpg`;
            } else {
                thumbnailUrl = `https://via.placeholder.com/640x360.png?text=Deleted`;
            }

            metaHtml = `<span class="badge deleted">Deleted</span>`;

            card.innerHTML = `
                <div class="thumbnail-container">
                    <img src="${thumbnailUrl}" alt="Thumbnail" loading="lazy" onerror="this.src='https://via.placeholder.com/640x360.png?text=No+Thumbnail'">
                    <div class="play-overlay">
                        <div class="play-btn"><i class='bx bx-info-circle'></i></div>
                    </div>
                </div>
                <div class="card-content">
                    <h3 class="card-title">${video.title}</h3>
                    <div class="card-meta">
                        <span>${video.original_upload_time.split(' ')[0]} ${video.original_upload_time.split(' ')[1]}</span>
                        ${metaHtml}
                    </div>
                </div>
            `;

            // Open modal on click
            card.addEventListener('click', () => {
                openModal(video);
            });
        }

        grid.appendChild(card);
    });

    // Add "More Videos" button if needed for Active tab
    if (showMoreButton) {
        const moreBtnContainer = document.createElement('div');
        moreBtnContainer.style.gridColumn = "1 / -1";
        moreBtnContainer.style.textAlign = "center";
        moreBtnContainer.style.marginTop = "2rem";

        moreBtnContainer.innerHTML = `
            <a href="https://www.youtube.com/@SandeepSeminars/videos" target="_blank" class="btn-watch" style="background-color: var(--accent); display: inline-block; padding: 1rem 3rem; font-size: 1.1rem; text-decoration: none;">View More on YouTube</a>
        `;
        grid.appendChild(moreBtnContainer);
    }
}

function openModal(video) {
    const modal = document.getElementById('video-modal');
    const modalBody = document.getElementById('modal-body');

    let backupLink = '';
    if (video.backup_video_id) {
        backupLink = `<a href="https://youtube.com/watch?v=${video.backup_video_id}" target="_blank" class="btn-watch">Watch Backup Video</a>`;
    } else {
        backupLink = `<p style="color: var(--danger); margin-top: 1rem;">No backup was available for this video.</p>`;
    }

    modalBody.innerHTML = `
        <div class="modal-body-content">
            <h2>${video.title}</h2>
            <div class="detail-row">
                <span>Original Upload (IST)</span>
                <span>${video.original_upload_time}</span>
            </div>
            <div class="detail-row">
                <span>Exact Deletion Time (IST)</span>
                <span>${video.deleted_time}</span>
            </div>
            <div class="detail-row">
                <span>Status</span>
                <span style="color: var(--danger)">Deleted / Private</span>
            </div>
            ${backupLink}
        </div>
    `;

    modal.classList.add('active');
}

function closeModal() {
    const modal = document.getElementById('video-modal');
    modal.classList.remove('active');
}
