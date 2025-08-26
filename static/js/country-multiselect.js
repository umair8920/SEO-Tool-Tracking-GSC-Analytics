/***********************************************
 * country-multiselect.js
 *
 * Multi-select approach for countries with a search box,
 * supporting:
 *  - Lowercase country codes
 *  - Top five countries at the top (alphabetical),
 *    rest alphabetical afterwards
 *  - Click outside to close
 *  - Previously selected remain checked
 *  - Display selected codes in a hidden input
 *  - DOES NOT re-render on search, instead hides/shows labels
 ***********************************************/

/** 1) Top countries in lowercase. */
const TOP_COUNTRIES = ["usa", "ind", "gbr", "can", "aus"];

/** 2) Full list of countries in lowercase codes. */
const ALL_COUNTRIES = [
    { code: "afg", name: "Afghanistan" },
    { code: "ala", name: "Åland Islands" },
    { code: "alb", name: "Albania" },
    { code: "dza", name: "Algeria" },
    { code: "asm", name: "American Samoa" },
    { code: "and", name: "Andorra" },
    { code: "ago", name: "Angola" },
    { code: "aia", name: "Anguilla" },
    { code: "ata", name: "Antarctica" },
    { code: "atg", name: "Antigua and Barbuda" },
    { code: "arg", name: "Argentina" },
    { code: "arm", name: "Armenia" },
    { code: "abw", name: "Aruba" },
    { code: "aus", name: "Australia" },
    { code: "aut", name: "Austria" },
    { code: "aze", name: "Azerbaijan" },
    { code: "bhs", name: "Bahamas" },
    { code: "bhr", name: "Bahrain" },
    { code: "bgd", name: "Bangladesh" },
    { code: "brb", name: "Barbados" },
    { code: "blr", name: "Belarus" },
    { code: "bel", name: "Belgium" },
    { code: "blz", name: "Belize" },
    { code: "ben", name: "Benin" },
    { code: "btn", name: "Bhutan" },
    { code: "bol", name: "Bolivia" },
    { code: "bih", name: "Bosnia and Herzegovina" },
    { code: "bwa", name: "Botswana" },
    { code: "bra", name: "Brazil" },
    { code: "brn", name: "Brunei Darussalam" },
    { code: "bgr", name: "Bulgaria" },
    { code: "bfa", name: "Burkina Faso" },
    { code: "bdi", name: "Burundi" },
    { code: "cpv", name: "Cabo Verde" },
    { code: "khm", name: "Cambodia" },
    { code: "cmr", name: "Cameroon" },
    { code: "can", name: "Canada" },
    { code: "caf", name: "Central African Republic" },
    { code: "tcd", name: "Chad" },
    { code: "chl", name: "Chile" },
    { code: "chn", name: "China" },
    { code: "col", name: "Colombia" },
    { code: "cod", name: "Congo (Democratic Republic)" },
    { code: "cog", name: "Congo (Republic)" },
    { code: "cri", name: "Costa Rica" },
    { code: "hrv", name: "Croatia" },
    { code: "cub", name: "Cuba" },
    { code: "cyp", name: "Cyprus" },
    { code: "cze", name: "Czechia" },
    { code: "dnk", name: "Denmark" },
    { code: "dji", name: "Djibouti" },
    { code: "ecu", name: "Ecuador" },
    { code: "egy", name: "Egypt" },
    { code: "slv", name: "El Salvador" },
    { code: "est", name: "Estonia" },
    { code: "eth", name: "Ethiopia" },
    { code: "fin", name: "Finland" },
    { code: "fra", name: "France" },
    { code: "deu", name: "Germany" },
    { code: "gha", name: "Ghana" },
    { code: "grc", name: "Greece" },
    { code: "gbr", name: "United Kingdom" },
    { code: "hkg", name: "Hong Kong" },
    { code: "hun", name: "Hungary" },
    { code: "ind", name: "India" },
    { code: "idn", name: "Indonesia" },
    { code: "irl", name: "Ireland" },
    { code: "isr", name: "Israel" },
    { code: "ita", name: "Italy" },
    { code: "jpn", name: "Japan" },
    { code: "ken", name: "Kenya" },
    { code: "kor", name: "South Korea" },
    { code: "lka", name: "Sri Lanka" },
    { code: "lux", name: "Luxembourg" },
    { code: "mys", name: "Malaysia" },
    { code: "mex", name: "Mexico" },
    { code: "nld", name: "Netherlands" },
    { code: "nzl", name: "New Zealand" },
    { code: "nga", name: "Nigeria" },
    { code: "nor", name: "Norway" },
    { code: "omn", name: "Oman" },
    { code: "pak", name: "Pakistan" },
    { code: "per", name: "Peru" },
    { code: "phl", name: "Philippines" },
    { code: "pol", name: "Poland" },
    { code: "prt", name: "Portugal" },
    { code: "qat", name: "Qatar" },
    { code: "rou", name: "Romania" },
    { code: "rus", name: "Russia" },
    { code: "sau", name: "Saudi Arabia" },
    { code: "sgp", name: "Singapore" },
    { code: "zaf", name: "South Africa" },
    { code: "esp", name: "Spain" },
    { code: "swe", name: "Sweden" },
    { code: "che", name: "Switzerland" },
    { code: "tha", name: "Thailand" },
    { code: "tur", name: "Turkey" },
    { code: "uga", name: "Uganda" },
    { code: "ukr", name: "Ukraine" },
    { code: "are", name: "United Arab Emirates" },
    { code: "usa", name: "United States of America" },
    { code: "ury", name: "Uruguay" },
    { code: "ven", name: "Venezuela" },
    { code: "vnm", name: "Vietnam" },
    { code: "zmb", name: "Zambia" },
    { code: "zwe", name: "Zimbabwe" }
  ];
  

/** 
 * Combined array that places top countries first (alphabetical among themselves),
 * then the rest alphabetical afterwards.
 */
let combinedCountries = [];

/** Initialize the countries on script load. */
(function initCountries() {
  const top = [];
  const rest = [];

  ALL_COUNTRIES.forEach(c => {
    if (TOP_COUNTRIES.includes(c.code)) {
      top.push(c);
    } else {
      rest.push(c);
    }
  });

  // Sort top by name
  top.sort((a, b) => a.name.localeCompare(b.name));
  // Sort rest by name
  rest.sort((a, b) => a.name.localeCompare(b.name));

  // Merge
  combinedCountries = [...top, ...rest];
})();

/**
 * Render the entire country list as checkboxes in container,
 * checking any codes that are already in hiddenInput.value.
 * 
 * We do this ONCE, so that search just hides/shows label rows
 * rather than re-rendering and losing previous checks.
 */
function renderCountryList(container, hiddenInput) {
  container.innerHTML = ""; // clear old

  combinedCountries.forEach(c => {
    const label = document.createElement("label");
    label.className = "flex items-center space-x-2 mb-1 cursor-pointer";
    // Store code in a data attribute for filtering
    label.dataset.countryCode = c.code.toLowerCase();
    label.dataset.countryName = c.name.toLowerCase();

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.value = c.code;
    checkbox.className = "country-checkbox";

    // If hiddenInput has c.code, check it
    const selectedCodes = hiddenInput.value ? hiddenInput.value.split(",") : [];
    if (selectedCodes.includes(c.code)) {
      checkbox.checked = true;
    }

    // On change, update hidden input
    checkbox.addEventListener("change", () => {
      updateSelectedCountries(hiddenInput, container);
    });

    label.appendChild(checkbox);

    const span = document.createElement("span");
    span.textContent = `${c.name} (${c.code})`;
    label.appendChild(span);

    container.appendChild(label);
  });
}

/**
 * Filter the existing label rows in the container by showing/hiding them,
 * instead of re-rendering. This preserves previous check states.
 */
function filterCountriesInList(input) {
  const row = input.closest(".cluster-row");
  const listDiv = row.querySelector(".country-list");

  // Show if hidden
  listDiv.classList.remove("hidden");

  const query = input.value.toLowerCase();

  // For each label row, check if name or code includes the query
  const labels = listDiv.querySelectorAll("label");
  labels.forEach(label => {
    const code = label.dataset.countryCode; // e.g. "usa"
    const name = label.dataset.countryName; // e.g. "united states of america"
    if (name.includes(query) || code.includes(query)) {
      label.style.display = "flex"; // show
    } else {
      label.style.display = "none"; // hide
    }
  });
}

/**
 * Update the hidden input with selected codes 
 * whenever checkboxes are changed.
 * Optionally, show them in the search box as well.
 */
function updateSelectedCountries(hiddenInput, container) {
  const checkboxes = container.querySelectorAll(".country-checkbox");
  const selected = [];
  checkboxes.forEach(cb => {
    if (cb.checked) {
      selected.push(cb.value);
    }
  });
  hiddenInput.value = selected.join(",");

  // If we want to reflect them in the search box placeholder:
  const row = container.closest(".cluster-row");
  const searchBox = row.querySelector(".search-box");
  if (searchBox) {
    if (selected.length > 0) {
      searchBox.placeholder = `Selected: ${selected.join(", ")}`;
    } else {
      searchBox.placeholder = "Search countries...";
    }
  }
}

/**
 * When user clicks outside the .country-list or .search-box,
 * we close the .country-list if open.
 */
document.addEventListener("click", function (e) {
  // If the click is not inside any cluster-row's search box or country-list,
  // we close all .country-list elements.
  const allLists = document.querySelectorAll(".country-list");
  allLists.forEach(listDiv => {
    if (!listDiv.contains(e.target)) {
      // Also check if the user didn't click on the search box
      const row = listDiv.closest(".cluster-row");
      if (row) {
        const searchBox = row.querySelector(".search-box");
        // If click is not inside searchBox
        if (searchBox && !searchBox.contains(e.target) && e.target !== searchBox) {
          listDiv.classList.add("hidden");
        }
      }
    }
  });
});
