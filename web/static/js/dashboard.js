/* dashboard.js — vanilla JS only, no frameworks */

'use strict';

// Highlight active nav link based on URL
document.addEventListener('DOMContentLoaded', function () {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-tool, .nav-home').forEach(a => {
    if (a.getAttribute('href') === path) {
      a.classList.add('active');
    }
  });
});
