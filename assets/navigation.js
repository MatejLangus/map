
document.addEventListener("DOMContentLoaded", function() {
  // Insert labels HTML into placeholder
  document.getElementById("navigation-placeholder").innerHTML = `<aside class='sidebar-labels'><h2>Navigacija</h2>
<div class='first-items'><h3>Kategorija:</h3><ul class='label-list'>
<li><a class='label-name' href='https:///search/labels/boat/'>boat</a></li>
<li><a class='label-name' href='https:///search/labels/cross-country-ski/'>cross_country_ski</a></li>
<li><a class='label-name' href='https:///search/labels/drive/'>drive</a></li>
<li><a class='label-name' href='https:///search/labels/gravel-bike/'>gravel_bike</a></li>
<li><a class='label-name' href='https:///search/labels/hike/'>hike</a></li>
<li><a class='label-name' href='https:///search/labels/inline-skate/'>inline_skate</a></li>
<li><a class='label-name' href='https:///search/labels/mountain-bike/'>mountain_bike</a></li>
<li><a class='label-name' href='https:///search/labels/other/'>other</a></li>
<li><a class='label-name' href='https:///search/labels/ride/'>ride</a></li>
<li><a class='label-name' href='https:///search/labels/roadtrip/'>roadtrip</a></li>
<li><a class='label-name' href='https:///search/labels/run/'>run</a></li>
<li><a class='label-name' href='https:///search/labels/ski/'>ski</a></li>
<li><a class='label-name' href='https:///search/labels/touring-ski/'>touring_ski</a></li>
<li><a class='label-name' href='https:///search/labels/trail-run/'>trail_run</a></li>
<li><a class='label-name' href='https:///search/labels/walk/'>walk</a></li>
</ul>
</div>
</aside>`;

  // Add state remembering for all <details>
  document.querySelectorAll("#navigation-placeholder details").forEach(function(det, idx) {
    var key = "navigation-state-" + idx;

    // Restore state from sessionStorage
    if (sessionStorage.getItem(key) === "open") {
      det.setAttribute("open", "");
    } else if (sessionStorage.getItem(key) === "closed") {
      det.removeAttribute("open");
    }

    // Save state when toggled
    det.addEventListener("toggle", function() {
      sessionStorage.setItem(key, det.open ? "open" : "closed");
    });
  });
});
