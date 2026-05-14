// Dev login card — displays test personas on the login page
(function () {
	// Only run on the login page
	if (window.location.pathname !== '/login') return;

	// Production safety: only render when the site is in developer mode.
	// frappe.boot.developer_mode mirrors `frappe.conf.developer_mode`, which
	// is 1 on dev sites and 0 on prod. The optional chaining defaults to
	// "hide" if boot isn't present for any reason — safer to lose the dev
	// affordance than to leak test credentials onto a prod login page.
	if (!(window.frappe && window.frappe.boot && window.frappe.boot.developer_mode)) return;

	var PERSONAS = [
		{ email: 'pro@test.com', password: 'TestUser@2026!', name: 'Sarah Professional', tag: 'Professional — 20 CEU credits' },
		{ email: 'company-admin@test.com', password: 'TestUser@2026!', name: 'Mike Manager', tag: 'Company Admin — 80 pool credits' },
		{ email: 'company-employee@test.com', password: 'TestUser@2026!', name: 'Lisa Employee', tag: 'Company Employee — uses pool' },
		{ email: 'ppt@test.com', password: 'TestUser@2026!', name: 'Pat PPTEmployee', tag: 'PPT Employee — free access' },
		{ email: 'broke@test.com', password: 'TestUser@2026!', name: 'Brooke Nocredits', tag: 'Professional — 0.5 credits (low)' },
	];

	function fillCredentials(email, password) {
		var emailInput = document.getElementById('login_email');
		var passwordInput = document.getElementById('login_password');
		if (emailInput) {
			emailInput.value = email;
			emailInput.dispatchEvent(new Event('change', { bubbles: true }));
		}
		if (passwordInput) {
			passwordInput.value = password;
			passwordInput.dispatchEvent(new Event('change', { bubbles: true }));
		}
	}

	function createDevLoginCard() {
		var loginBox = document.querySelector('.page-card');
		if (!loginBox) return;

		var rowsHtml = '';
		for (var i = 0; i < PERSONAS.length; i++) {
			rowsHtml +=
				'<button class="dev-persona-btn" data-index="' + i + '" style="' +
					'display: block;' +
					'width: 100%;' +
					'text-align: left;' +
					'background: white;' +
					'border: 1px solid #cce5f0;' +
					'border-radius: 6px;' +
					'padding: 0.5rem 0.75rem;' +
					'margin-bottom: 0.4rem;' +
					'cursor: pointer;' +
					'font-family: inherit;' +
					'font-size: 0.8rem;' +
					'line-height: 1.4;' +
					'transition: background 0.15s;' +
				'">' +
					'<span style="display: block; font-weight: 600; color: #0b6685;">' + PERSONAS[i].name + '</span>' +
					'<span style="display: block; color: #6b7280; font-size: 0.75rem;">' + PERSONAS[i].tag + '</span>' +
				'</button>';
		}

		var card = document.createElement('div');
		card.id = 'dev-login-card';
		card.innerHTML =
			'<div style="' +
				'margin-top: 1rem;' +
				'padding: 1rem 1.25rem;' +
				'background: #f0f9fc;' +
				'border: 1px solid #0b6685;' +
				'border-radius: 8px;' +
				'font-family: inherit;' +
				'font-size: 0.875rem;' +
			'">' +
				'<div style="' +
					'font-weight: 700;' +
					'color: #0b6685;' +
					'margin-bottom: 0.75rem;' +
					'font-size: 0.9rem;' +
				'">Test Logins</div>' +
				rowsHtml +
			'</div>';

		loginBox.appendChild(card);

		// Wire up persona buttons
		var buttons = card.querySelectorAll('.dev-persona-btn');
		for (var j = 0; j < buttons.length; j++) {
			buttons[j].addEventListener('mouseenter', function () {
				this.style.background = '#e0f2fa';
			});
			buttons[j].addEventListener('mouseleave', function () {
				this.style.background = 'white';
			});
			buttons[j].addEventListener('click', function () {
				var idx = parseInt(this.getAttribute('data-index'), 10);
				fillCredentials(PERSONAS[idx].email, PERSONAS[idx].password);
			});
		}
	}

	if (document.readyState === 'loading') {
		document.addEventListener('DOMContentLoaded', createDevLoginCard);
	} else {
		createDevLoginCard();
	}
})();
