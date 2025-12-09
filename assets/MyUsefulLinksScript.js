const usefulLinks = [
    {
        "title": "maPZS",
        "url": "https://mapzs.pzs.si/home/trails",
        "description": "Zemljevid slovenskih planinskih poti.",
        "favicon": "https://mapzs.pzs.si/assets/icons/favicon-32x32.png"
    },
    {
        "title": "Gorski užitki – Metod Langus",
        "url": "https://metodlangus.github.io/",
        "description": "Gorniški blog",
        "favicon": "https://metodlangus.github.io/photos/favicon.ico"
    }
];


const container = document.getElementById('useful-links-container');
let html = '<ul class="useful-links">';

usefulLinks.forEach((link) => {
    html += `
        <li style="margin-bottom:15px; position:relative;">
            <img src="${link.favicon}" alt="" style="width:16px;height:16px;vertical-align:middle;margin-right:5px;">
            <a href="${link.url}" target="_blank">${link.title}</a>
            <br>
            <small>${link.description}</small>
        </li>
    `;
});

html += '</ul>';
container.innerHTML = html;
