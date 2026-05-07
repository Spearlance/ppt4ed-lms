import { defineStore } from 'pinia'
import { createResource } from 'frappe-ui'
import { usersStore } from './user'
import { computed, reactive, ref } from 'vue'

export const sessionStore = defineStore('lms-session', () => {
	let { userResource } = usersStore()
	const brand = reactive({})

	function sessionUser() {
		let cookies = new URLSearchParams(document.cookie.split('; ').join('&'))
		let _sessionUser = cookies.get('user_id')
		if (_sessionUser === 'Guest') {
			_sessionUser = null
		} else {
			userResource.reload()
		}
		return _sessionUser
	}

	let user = ref(sessionUser())
	const isLoggedIn = computed(() => !!user.value)

	const logout = createResource({
		url: 'logout',
		onSuccess() {
			userResource.reset()
			user.value = null
			window.location.reload()
		},
	})

	const branding = createResource({
		url: 'lms.lms.api.get_branding',
		cache: 'brand',
		auto: true,
		onSuccess(data) {
			brand.name = data.app_name
			// `get_branding` returns app_logo/favicon as File objects, not URL
			// strings — extract `.file_url` so consumers can drop these
			// straight into <img :src>. Falls back gracefully if absent.
			brand.logo = data.app_logo?.file_url || null
			brand.favicon =
				data.favicon?.file_url || '/assets/lms/frontend/learning.svg'
		},
	})

	return {
		user,
		isLoggedIn,
		logout,
		brand,
		branding,
	}
})
