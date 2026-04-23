/**
 * VKS Legal AI — Documentation Interactive Scripts
 */

// ============ SIDEBAR MOBILE TOGGLE ============
function toggleSidebar() {
  document.querySelector('.docs-sidebar').classList.toggle('open');
}

// Close sidebar on outside click (mobile)
document.addEventListener('click', (e) => {
  const sidebar = document.querySelector('.docs-sidebar');
  const toggle = document.querySelector('.mobile-toggle');
  if (sidebar && sidebar.classList.contains('open') && !sidebar.contains(e.target) && !toggle.contains(e.target)) {
    sidebar.classList.remove('open');
  }
});

// ============ COPY CODE ============
function copyCode(btn) {
  const block = btn.closest('.code-block');
  const code = block.querySelector('pre').textContent;
  navigator.clipboard.writeText(code).then(() => {
    btn.textContent = '✓ Copied!';
    btn.classList.add('copied');
    setTimeout(() => {
      btn.textContent = 'Copy';
      btn.classList.remove('copied');
    }, 2000);
  });
}

// ============ ENDPOINT TOGGLE ============
function toggleEndpoint(header) {
  const body = header.nextElementSibling;
  const card = header.closest('.endpoint-card');
  const isOpen = body.classList.contains('open');

  // Close all others
  document.querySelectorAll('.endpoint-body.open').forEach(b => b.classList.remove('open'));
  document.querySelectorAll('.endpoint-card.active').forEach(c => c.classList.remove('active'));

  if (!isOpen) {
    body.classList.add('open');
    card.classList.add('active');
  }
}

// ============ TABS ============
function switchTab(tabGroup, tabIndex) {
  const group = document.querySelector(`[data-tab-group="${tabGroup}"]`);
  if (!group) return;

  group.querySelectorAll('.tab-btn').forEach((btn, i) => {
    btn.classList.toggle('active', i === tabIndex);
  });

  group.querySelectorAll('.tab-panel').forEach((panel, i) => {
    panel.classList.toggle('active', i === tabIndex);
  });
}

// ============ SMOOTH SCROLL FOR ANCHOR LINKS ============
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', (e) => {
      e.preventDefault();
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth' });
        // Update active nav
        document.querySelectorAll('.docs-nav-link').forEach(l => l.classList.remove('active'));
        anchor.classList.add('active');
      }
    });
  });

  // Highlight active nav on scroll
  const sections = document.querySelectorAll('h2[id], h3[id]');
  const navLinks = document.querySelectorAll('.docs-nav-link[href^="#"]');

  if (sections.length && navLinks.length) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('href') === '#' + entry.target.id);
          });
        }
      });
    }, { rootMargin: '-100px 0px -60% 0px' });

    sections.forEach(section => observer.observe(section));
  }
});

// ============ SEARCH (Simple) ============
function searchDocs(query) {
  const q = query.toLowerCase().trim();
  const sections = document.querySelectorAll('.docs-content > *');

  if (!q) {
    sections.forEach(s => s.style.display = '');
    return;
  }

  sections.forEach(section => {
    const text = section.textContent.toLowerCase();
    section.style.display = text.includes(q) ? '' : 'none';
  });
}
