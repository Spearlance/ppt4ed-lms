<template>
	<div v-if="batch.data" class="">
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between bg-surface-white px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs :items="breadcrumbs" />
			<div v-if="tabIndex == 5 && isAdmin" class="flex items-center space-x-2">
				<Badge v-if="childRef?.isDirty" theme="orange">
					{{ __('Not Saved') }}
				</Badge>
				<Button @click="childRef.deleteEvent()">
					<template #icon>
						<Trash2 class="w-4 h-4 stroke-1.5" />
					</template>
				</Button>
				<Button variant="solid" @click="childRef.submitEvent()">
					{{ __('Save') }}
				</Button>
			</div>
			<Dropdown
				v-else-if="isAdmin && batchMenu.length"
				:options="batchMenu"
				placement="left"
				side="left"
			>
				<template v-slot="{ open }">
					<Button variant="ghost">
						<template #icon>
							<EllipsisVertical class="w-4 h-4 stroke-1.5" />
						</template>
					</Button>
				</template>
			</Dropdown>
		</header>
		<div>
			<EventOverview v-if="!isAdmin && !isStudent" :batch="batch" />
			<div v-else>
				<Tabs v-if="tabs.length" :tabs="tabs" v-model="tabIndex">
					<template #tab-panel="{ tab }">
						<div
							v-if="tab.label == 'Discussions'"
							class="w-[90%] lg:w-[75%] mx-auto mt-5"
						>
							<Discussions
								doctype="LMS Event"
								:docname="batch.data.name"
								:title="__('Discussions')"
								:key="batch.data.name"
								:singleThread="true"
								:scrollToBottom="false"
							/>
						</div>

						<Announcements
							v-else-if="tab.label == 'Announcements'"
							:batch="batch"
							:canPost="canMakeAnnouncement()"
							@open-modal="openAnnouncementModal"
							ref="announcementsRef"
						/>

						<component
							v-else
							:is="tab.component"
							:batch="batch"
							ref="childRef"
						/>
					</template>
				</Tabs>
			</div>
		</div>
	</div>
	<BulkCertificates
		v-if="batch.data"
		v-model="openCertificateDialog"
		:batch="batch.data"
	/>
	<AnnouncementModal
		v-if="batch.data"
		v-model="showAnnouncementModal"
		:event="batch.data.name"
		:eventTitle="batch.data.title"
		@posted="announcementsRef?.reload?.()"
	/>
	<EventSurveyQRModal
		v-if="batch.data"
		v-model="showSurveyQRModal"
		:event="batch.data.name"
		:eventTitle="batch.data.title"
	/>
</template>
<script setup>
import {
	ClipboardList,
	ClipboardPen,
	EllipsisVertical,
	Laptop,
	List,
	Mail,
	MessageCircle,
	SendIcon,
	Settings2,
	Trash2,
	TrendingUp,
} from 'lucide-vue-next'
import { computed, inject, markRaw, onMounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	Dropdown,
	Tabs,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import AdminEventDashboard from '@/pages/Events/components/AdminEventDashboard.vue'
import StudentEventDashboard from '@/pages/Events/components/EventDashboard.vue'
import EventOverview from '@/pages/Events/EventOverview.vue'
import LiveClass from '@/pages/Events/components/LiveClass.vue'
import Announcements from '@/pages/Events/components/Announcements.vue'
import AnnouncementModal from '@/pages/Events/components/AnnouncementModal.vue'
import EventSurvey from '@/pages/Events/components/EventSurvey.vue'
import EventSurveyQRModal from '@/pages/Events/components/EventSurveyQRModal.vue'
import EventForm from '@/pages/Events/EventForm.vue'
import BulkCertificates from '@/pages/Events/components/BulkCertificates.vue'
import Discussions from '@/components/Discussions.vue'

const router = useRouter()
const route = useRoute()
const { brand } = sessionStore()
const user = inject('$user')
const childRef = ref(null)
const announcementsRef = ref(null)
const tabIndex = ref(0)
const tabs = ref([])
const openCertificateDialog = ref(false)
const showAnnouncementModal = ref(false)
const showSurveyQRModal = ref(false)
const readOnlyMode = window.read_only_mode

const props = defineProps({
	eventName: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	const status = route.query.payment
	if (status === 'success') {
		toast.success(__('Payment received — registering you now'))
		setTimeout(() => batch.reload(), 2000)
	} else if (status === 'cancelled') {
		toast.info(__('Payment cancelled'))
	}
	if (status) {
		router.replace({ query: { ...route.query, payment: undefined } })
	}
})

const updateTabIndex = () => {
	const hash = route.hash
	if (hash) {
		tabs.value.forEach((tab, index) => {
			if (tab.label?.toLowerCase() === hash.replace('#', '')) {
				tabIndex.value = index
			}
		})
	}
}

watch(tabIndex, () => {
	const tab = tabs.value[tabIndex.value]
	if (tab.label != route.hash.replace('#', '')) {
		router.push({ ...route, hash: `#${tab.label.toLowerCase()}` })
	}
})

const batch = createResource({
	url: 'lms.lms.utils.get_event_details',
	cache: ['event', props.eventName],
	params: {
		batch: props.eventName,
	},
	auto: true,
	onSuccess: (data) => {
		if (!data) {
			router.push({ name: 'Events' })
		}
	},
})

watch(batch, () => {
	updateTabs()
	updateTabIndex()
})

watch(
	() => route.hash,
	() => updateTabIndex()
)

const updateTabs = () => {
	addToTabs('Overview', markRaw(EventOverview), List)
	if (!user.data) return
	if (isAdmin.value) {
		addToTabs('Dashboard', markRaw(AdminEventDashboard), TrendingUp)
	} else if (isStudent.value) {
		addToTabs('Dashboard', markRaw(StudentEventDashboard), ClipboardPen)
	}
	addToTabs('Classes', markRaw(LiveClass), Laptop)
	addToTabs('Announcements', markRaw(Announcements), Mail)
	if (
		batch.data?.survey_quiz &&
		(isAdmin.value || (isStudent.value && batch.data?.survey_open))
	) {
		addToTabs('Survey', markRaw(EventSurvey), ClipboardList)
	}
	addToTabs('Discussions', markRaw(Discussions), MessageCircle)
	if (isAdmin.value) {
		addToTabs('Settings', markRaw(EventForm), Settings2)
	}
}

const addToTabs = (label, component, icon) => {
	if (!tabs.value.some((tab) => tab.label === label)) {
		tabs.value.push({
			label,
			component,
			icon,
		})
	}
}

const isAdmin = computed(() => {
	return user.data?.is_moderator
})

const isStudent = computed(() => {
	return batch.data?.students?.includes(user.data?.name)
})

const openAnnouncementModal = () => {
	showAnnouncementModal.value = true
}

const canMakeAnnouncement = () => {
	if (readOnlyMode) return false
	if (!batch.data) return false
	if (user.data?.is_moderator) return true
	return batch.data.instructors?.some(
		(i) => i.name === user.data?.name
	)
}

const batchMenu = computed(() => {
	if (
		!batch.data?.certification &&
		!canMakeAnnouncement() &&
		!batch.data?.survey_quiz
	) {
		return []
	}
	let options = [
		{
			label: __('Generate Certificates'),
			onClick() {
				openCertificateDialog.value = true
			},
			condition: () => batch.data?.certification,
		},
		{
			label: __('Make an Announcement'),
			onClick() {
				openAnnouncementModal()
			},
			condition: () => canMakeAnnouncement(),
		},
		{
			label: __('Download Survey QR Code'),
			onClick() {
				showSurveyQRModal.value = true
			},
			condition: () => batch.data?.survey_quiz && isAdmin.value,
		},
	]
	return options
})

const breadcrumbs = computed(() => {
	let crumbs = [{ label: __('Events'), route: { name: 'Events' } }]
	crumbs.push({
		label: batch?.data?.title,
		route: { name: 'EventDetail', params: { eventName: batch?.data?.name } },
	})
	return crumbs
})

usePageMeta(() => {
	return {
		title: batch?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style>
.event-description p {
	margin-bottom: 1rem;
	line-height: 1.7;
}

.event-description li {
	line-height: 1.7;
}

.event-description ol {
	list-style: auto;
	margin: revert;
	padding: revert;
}

.event-description strong {
	font-weight: 600;
	color: theme('colors.gray.900') !important;
}
</style>
