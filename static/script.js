/* ============================================
   সবুজ বই — Custom JavaScript
   ============================================ */

// Smooth scroll for internal links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener("click", function (e) {
        e.preventDefault();
        document.querySelector(this.getAttribute("href")).scrollIntoView({
            behavior: "smooth"
        });
    });
});

// Auto-dismiss alerts after 5 seconds
document.querySelectorAll('.alert').forEach(alert => {
    setTimeout(() => {
        alert.classList.add('fade');
        setTimeout(() => alert.remove(), 500);
    }, 5000);
});

// Feedback form validation
const feedbackForm = document.querySelector('form[action="/feedback"]');
if (feedbackForm) {
    feedbackForm.addEventListener("submit", function (e) {
        const name = document.getElementById("name").value.trim();
        const feedback = document.getElementById("feedback").value.trim();

        if (!name || !feedback) {
            e.preventDefault();
            alert("⚠️ অনুগ্রহ করে নাম এবং মতামত পূরণ করুন।");
        }
    });
}

// Navbar active link highlight
const currentPath = window.location.pathname;
document.querySelectorAll(".navbar-nav .nav-link").forEach(link => {
    if (link.getAttribute("href") === currentPath) {
        link.classList.add("active");
    }
});

// Back to top button
const backToTopBtn = document.createElement("button");
backToTopBtn.innerText = "⬆️ উপরে যান";
backToTopBtn.className = "btn btn-secondary";
backToTopBtn.style.position = "fixed";
backToTopBtn.style.bottom = "20px";
backToTopBtn.style.right = "20px";
backToTopBtn.style.display = "none";
document.body.appendChild(backToTopBtn);

window.addEventListener("scroll", () => {
    if (window.scrollY > 200) {
        backToTopBtn.style.display = "block";
    } else {
        backToTopBtn.style.display = "none";
    }
});

backToTopBtn.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
});
