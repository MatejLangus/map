const WindowBaseUrl = window.location.origin;
const initPhotos = 3; // Determine range of photos to be shown on slideshows and in posts
const initMapPhotos = 3; // Determine range of photos to be shown on map

// Format date
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.post-date').forEach(function (el) {
    const date = new Date(el.dataset.date);
    const formatted = date.toLocaleDateString('sl-SI', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric'
    });
    el.textContent = formatted;
  });
});



// Removes images from the post and slideshow if their `data-skip` attribute is not within the allowed range.
document.addEventListener("DOMContentLoaded", function() {
        const elements = [
            ...document.querySelectorAll('td.tr-caption'),
            ...document.querySelectorAll('.separator')
        ];

        const PhotosRange = localStorage.getItem('photosSliderValue') || initPhotos; // Default value if not set

        // Function to process the `data-skip` attribute and check the range
        function isWithinRange(dataSkip) {
            // Assign a default value to `data-skip` if undefined or "NA"
            if (dataSkip === "NA" || dataSkip === null || dataSkip === undefined) {
                dataSkip = "3"; // Assign a default value
            }

            // Replace placeholders in the `data-skip` values
            dataSkip = dataSkip
                .replace(/best/g, "0")
                .replace(/cover/g, "-1")
                .replace(/peak/g, "5"); // Remove all peaks to be displayed because of high priority

            // Split `data-skip` values by semicolon
            const dataSkipValues = dataSkip.split(";");

            // Convert values to numbers and filter out invalid ones
            const numericValues = dataSkipValues
                .map(value => parseFloat(value))
                .filter(value => !isNaN(value));

            // Find the smallest number
            const minValue = Math.min(...numericValues);

            // // Exclude if the only tag is `-2` (peak)
            // if (minValue === -2 && dataSkipValues.length === 1) {
            //     return false;
            // }

            // Check if the smallest number is greater than PhotosRange
            return minValue > PhotosRange ? 1 : 0;
        }

        // Iterate over all elements and process them
        elements.forEach(element => {
            const isCaption = element.classList.contains('tr-caption');
            const isSeparator = element.classList.contains('separator');

            if (isCaption) {
                // Process caption elements
                const title = element.textContent.trim();
                const link = element.closest('tr').previousElementSibling?.querySelector('a[href*="blogger.googleusercontent.com"]');
                if (link) {
                    link.setAttribute('data-title', title);
                }

                const img = element.closest('tr').previousElementSibling?.querySelector('a img');
                if (img && isWithinRange(img.getAttribute('data-skip'))) {
                    const table = element.closest('table');
                    if (table) table.remove();
                }
            } else if (isSeparator) {
                // Process separator elements
                const img = element.querySelector('img');
                const text = element.textContent.trim();

                if (img && isWithinRange(img.getAttribute('data-skip'))) {
                    element.remove();
                } else if (!img && !text) {
                    // Remove separator if no content and no images
                    element.remove();
      }
    }
  });
});



/* For togling label navigation bar */
document.addEventListener("DOMContentLoaded", function() {
  const showMoreBtn = document.querySelector(".show-more");
  const showLessBtn = document.querySelector(".show-less");
  const remainingItems = document.querySelector(".remaining-items");

  if (showMoreBtn && showLessBtn && remainingItems) {
    showMoreBtn.addEventListener("click", function() {
      remainingItems.classList.remove("hidden");
      showMoreBtn.classList.add("hidden");
      showLessBtn.classList.remove("hidden");
    });

    showLessBtn.addEventListener("click", function() {
      remainingItems.classList.add("hidden");
      showMoreBtn.classList.remove("hidden");
      showLessBtn.classList.add("hidden");
    });
  }
});


/* Searchbox */
let posts = [];

fetch(`${WindowBaseUrl}/data/all-posts.json`)
  .then(response => response.json())
  .then(data => {
    const entries = data.feed.entry || [];

    posts = entries.map((entry, i) => {
      const title = entry.title?.$t || `untitled-${i}`;
      const content = entry.content?.$t || "";
      const link = entry.link.find(l => l.rel === "alternate" && l.type === "text/html")?.href || "#";
      const thumbnail = entry.media$thumbnail?.url || "";

      return { title, content, link, thumbnail };
    });
  })
  .catch(error => {
    console.error("Napaka pri nalaganju Blogger feeda:", error);
  });

document.addEventListener("DOMContentLoaded", function () {
  const searchToggle = document.getElementById("searchToggle");
  const searchContainer = document.getElementById("searchContainer");
  const searchClose = document.getElementById("searchClose");
  const searchBox = document.getElementById("searchBox");
  const resultsContainer = document.getElementById("searchResults");

  // Toggle search container visibility
  searchToggle.addEventListener("click", () => {
    const isVisible = searchContainer.classList.toggle("visible");
    if (!isVisible) {
      closeSearchOverlay();
    } else {
      // Optionally focus input when opened
      searchBox.focus();
    }
  });

  // Close button inside search container clears and closes search
  searchClose.addEventListener("click", () => {
    closeSearchOverlay();
  });

  // Search input event
  searchBox.addEventListener("input", function () {
    const keyword = this.value.toLowerCase();
    resultsContainer.innerHTML = "";

    if (!keyword) {
      // If input cleared, hide results overlay
      resultsContainer.classList.add("overlay-hidden");
      resultsContainer.classList.remove("overlay-visible");
      return;
    }

    const filtered = posts.filter(post =>
      post.title.toLowerCase().includes(keyword) ||
      post.content.toLowerCase().includes(keyword)
    );

    if (filtered.length > 0) {
      let resultHTML = `
        <button class="close-button" onclick="closeSearchOverlay()">×</button>
        <h1>Prikaz objav, ki vsebujejo: ${keyword}</h1>
        <div class="search-posts-container">`;

      filtered.forEach(post => {
        resultHTML += `
          <div class="post-container">
            <a href="${post.link}" class="image-link">
              <div class="image-wrapper">
                ${post.thumbnail ? `<img src="${post.thumbnail.replace(/\/s\d+-c/, '/s300')}" alt="Thumbnail for ${post.title}" class="post-thumb">` : ""}
                <h3 class="overlay-title">${post.title}</h3>
              </div>
            </a>
          </div>`;
      });

      resultHTML += `</div>`;
      resultsContainer.innerHTML = resultHTML;

      // Show results overlay
      resultsContainer.classList.remove("overlay-hidden");
      resultsContainer.classList.add("overlay-visible");
    } else {
      // No results - hide overlay
      resultsContainer.classList.add("overlay-hidden");
      resultsContainer.classList.remove("overlay-visible");
    }
  });

  // Define closeSearchOverlay globally so button inside results can call it
  window.closeSearchOverlay = function () {
    resultsContainer.innerHTML = "";
    resultsContainer.classList.add("overlay-hidden");
    resultsContainer.classList.remove("overlay-visible");

    searchBox.value = "";
    searchContainer.classList.remove("visible");
  };
});


/* Toggle sidebar */
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    sidebar.classList.toggle("visible");
  }


/* Pagination */
document.addEventListener("DOMContentLoaded", function () {
    const entries = document.querySelectorAll(".photo-entry");
    const entriesPerPage = 12;
    const totalPages = Math.ceil(entries.length / entriesPerPage);
    const pager = document.getElementById("blog-pager");
    let currentPage = 1;

    if (!pager) {
        // console.error("Pagination container with ID 'blog-pager' not found.");
        return;
    }

    function redirectpage(page) {
        if (page < 1 || page > totalPages) return;
        currentPage = page;
        showPage(currentPage);
    }

    function showPage(page) {
        entries.forEach(entry => {
            entry.style.display = entry.getAttribute("data-page") == page ? "block" : "none";
        });
        renderPager(page);
    }

    function renderPager(page) {
        // Hide pager if only one page
        if (totalPages <= 1) {
            pager.style.display = "none";
            return;
        } else {
            pager.style.display = "flex";
        }

        pager.innerHTML = '';

        // Previous button
        pager.innerHTML += `<span class="displaypageNum"><a href="#" onclick="redirectpage(${page - 1}); return false" ${page === 1 ? 'style="pointer-events:none;opacity:0.5;"' : ''}>&laquo;</a></span>`;

        // First page
        if (page === 1) {
            pager.innerHTML += `<span class="pagecurrent">1</span>`;
        } else {
            pager.innerHTML += `<span class="displaypageNum"><a href="#" onclick="redirectpage(1); return false">1</a></span>`;
        }

        // Ellipsis before current range
        if (page > 3) {
            pager.innerHTML += `<span class="showpage ellipsis">...</span>`;
        }

        // Pages around current
        for (let i = page - 1; i <= page + 1; i++) {
            if (i > 1 && i < totalPages) {
                if (i === page) {
                    pager.innerHTML += `<span class="pagecurrent">${i}</span>`;
                } else {
                    pager.innerHTML += `<span class="displaypageNum"><a href="#" onclick="redirectpage(${i}); return false">${i}</a></span>`;
                }
            }
        }

        // Ellipsis after current range
        if (page < totalPages - 2) {
            pager.innerHTML += `<span class="showpage ellipsis">...</span>`;
        }

        // Last page
        if (page === totalPages) {
            pager.innerHTML += `<span class="pagecurrent">${totalPages}</span>`;
        } else {
            pager.innerHTML += `<span class="displaypageNum"><a href="#" onclick="redirectpage(${totalPages}); return false">${totalPages}</a></span>`;
        }

        // Next button
        pager.innerHTML += `<span class="displaypageNum"><a href="#" onclick="redirectpage(${page + 1}); return false" ${page === totalPages ? 'style="pointer-events:none;opacity:0.5;"' : ''}>&raquo;</a></span>`;
    }

    window.redirectpage = redirectpage;
    showPage(currentPage);
});


/* Gumb 'Na vrh' */
const btn = document.getElementById("backToTop");
window.addEventListener("scroll", () => {
  btn.style.display = window.scrollY > 400 ? "block" : "none";
});
btn.addEventListener("click", () => window.scrollTo({ top: 0, behavior: "smooth" }));