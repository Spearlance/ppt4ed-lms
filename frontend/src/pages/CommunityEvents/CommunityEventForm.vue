<template>
	<header
		class="sticky flex items-center justify-between top-0 z-10 border-b bg-surface-white px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
		<div class="flex items-center gap-2">
			<a
				v-if="event?.published && event?.route"
				:href="`/${event.route}`"
				target="_blank"
				class="text-sm text-ink-blue-9 hover:underline px-2"
			>
				{{ __('Open public page') }}
			</a>
			<Button v-if="event" variant="solid" :loading="saving" @click="save">
				{{ __('Save') }}
			</Button>
		</div>
	</header>

	<div class="px-5 py-4 max-w-5xl mx-auto" v-if="event">
		<div class="flex items-center gap-3 mb-4">
			<h1 class="text-xl font-semibold text-ink-gray-9">{{ event.title || __('Untitled Event') }}</h1>
			<Badge
				:theme="event.published ? 'green' : 'gray'"
				:label="event.published ? __('Published') : __('Draft')"
				size="sm"
			/>
		</div>

		<TabButtons
			:buttons="tabs"
			v-model="activeTab"
			class="mb-5"
		/>

		<div v-if="activeTab === 'settings'" class="space-y-5">
			<div class="grid grid-cols-2 gap-4">
				<FormControl
					v-model="event.title"
					:label="__('Title')"
					:required="true"
				/>
				<div class="flex items-center gap-3 pt-6">
					<Switch v-model="event.published" />
					<span class="text-sm text-ink-gray-7">
						{{ __('Published — public page is live') }}
					</span>
				</div>
			</div>

			<FormControl
				v-model="event.short_description"
				:label="__('Short Description')"
				type="textarea"
				:rows="2"
				:placeholder="__('One- or two-sentence summary shown on the public page.')"
			/>

			<div class="grid grid-cols-2 gap-4">
				<FormControl
					v-model="event.start_date"
					:label="__('Start Date')"
					type="date"
					:required="true"
				/>
				<FormControl
					v-model="event.end_date"
					:label="__('End Date')"
					type="date"
				/>
				<FormControl
					v-model="event.start_time"
					:label="__('Start Time')"
					type="time"
				/>
				<FormControl
					v-model="event.end_time"
					:label="__('End Time')"
					type="time"
				/>
			</div>

			<div class="grid grid-cols-2 gap-4">
				<FormControl
					v-model="event.location"
					:label="__('Location')"
					:placeholder="__('Address or \'Virtual\'')"
				/>
				<FormControl
					v-model="event.virtual_link"
					:label="__('Virtual Link')"
					:placeholder="__('Zoom/Meet/etc URL — included in the confirmation email')"
				/>
			</div>

			<div class="grid grid-cols-2 gap-4">
				<FormControl
					v-model.number="event.max_attendees"
					:label="__('Max Attendees (0 = unlimited)')"
					type="number"
					min="0"
				/>
				<FormControl
					v-model.number="event.additional_attendee_amount"
					:label="__('Donation per Extra Attendee (USD)')"
					type="number"
					min="0"
					step="0.01"
				/>
			</div>

			<div>
				<div class="mb-1.5 text-sm text-ink-gray-5">{{ __('Description') }}</div>
				<TextEditor
					:content="event.description || ''"
					@change="(val) => (event.description = val)"
					:editable="true"
					:fixedMenu="true"
					editorClass="prose-sm max-w-none border-b border-x bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[12rem] max-h-[20rem] overflow-auto"
				/>
			</div>

			<div class="border-t pt-4 flex items-center justify-between">
				<div class="text-sm text-ink-gray-6">
					{{ __('Public URL: ') }}
					<code class="text-ink-gray-9">/{{ event.route || `community-events/${event.name}` }}</code>
				</div>
				<Button theme="red" variant="ghost" @click="confirmDelete">
					{{ __('Delete Event') }}
				</Button>
			</div>
		</div>

		<div v-else-if="activeTab === 'registrations'">
			<div class="flex items-center justify-between mb-3">
				<div class="text-sm text-ink-gray-6">
					{{ registrations.data?.length || 0 }} {{ __('registration(s)') }}
				</div>
				<Button variant="ghost" @click="registrations.reload">
					<template #prefix>
						<RefreshCw class="w-4 h-4" />
					</template>
					{{ __('Refresh') }}
				</Button>
			</div>

			<div v-if="registrations.data?.length" class="border rounded-lg overflow-hidden">
				<table class="w-full text-sm">
					<thead class="bg-surface-gray-2 text-ink-gray-7">
						<tr>
							<th class="px-3 py-2 text-left font-medium">{{ __('Guardian') }}</th>
							<th class="px-3 py-2 text-left font-medium">{{ __('Attendees') }}</th>
							<th class="px-3 py-2 text-left font-medium">{{ __('Donation') }}</th>
							<th class="px-3 py-2 text-left font-medium">{{ __('Status') }}</th>
							<th class="px-3 py-2 text-left font-medium">{{ __('When') }}</th>
							<th class="px-3 py-2"></th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="reg in registrations.data"
							:key="reg.name"
							class="border-t hover:bg-surface-gray-1"
						>
							<td class="px-3 py-2.5">
								<div class="font-medium text-ink-gray-9">{{ reg.guardian_name }}</div>
								<div class="text-xs text-ink-gray-6">{{ reg.guardian_email }}</div>
								<div v-if="reg.guardian_phone" class="text-xs text-ink-gray-6">{{ reg.guardian_phone }}</div>
							</td>
							<td class="px-3 py-2.5">
								<div class="font-medium">{{ reg.attendee_count }}</div>
								<ul class="text-xs text-ink-gray-6 mt-0.5">
									<li v-for="a in reg.attendees" :key="a.attendee_name">
										{{ a.attendee_name }}<span v-if="a.attendee_age"> ({{ a.attendee_age }})</span>
									</li>
								</ul>
							</td>
							<td class="px-3 py-2.5">
								${{ Number(reg.donation_total || 0).toFixed(2) }}
							</td>
							<td class="px-3 py-2.5">
								<Badge
									:theme="statusTheme(reg.payment_status)"
									:label="reg.payment_status"
									size="sm"
								/>
							</td>
							<td class="px-3 py-2.5 text-ink-gray-6 whitespace-nowrap">
								{{ reg.registered_on ? dayjs(reg.registered_on).format('MMM D, h:mm a') : '' }}
							</td>
							<td class="px-3 py-2.5">
								<Button
									variant="ghost"
									theme="red"
									size="sm"
									@click="confirmDeleteReg(reg)"
								>
									{{ __('Delete') }}
								</Button>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-else-if="!registrations.loading" class="text-center py-12 text-ink-gray-6">
				{{ __('No registrations yet.') }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	call,
	createResource,
	FormControl,
	Switch,
	TabButtons,
	TextEditor,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { RefreshCw } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'

const props = defineProps({ slug: { type: String, required: true } })
const router = useRouter()
const dayjs = inject('$dayjs')
const { brand } = sessionStore()

const event = ref(null)
const saving = ref(false)
const activeTab = ref('settings')

const tabs = [
	{ label: __('Settings'), value: 'settings' },
	{ label: __('Registrations'), value: 'registrations' },
]

const eventResource = createResource({
	url: 'frappe.client.get',
	makeParams() {
		return { doctype: 'Community Event', name: props.slug }
	},
	onSuccess(data) {
		event.value = { ...data }
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not load event'))
	},
})

const registrations = createResource({
	url: 'lms.lms.community_event.get_community_event_registrations',
	makeParams() {
		return { event: props.slug }
	},
})

onMounted(() => {
	eventResource.fetch()
})

watch(activeTab, (val) => {
	if (val === 'registrations') registrations.reload()
})

const save = async () => {
	if (!event.value) return
	saving.value = true
	try {
		const updated = await call('frappe.client.set_value', {
			doctype: 'Community Event',
			name: event.value.name,
			fieldname: {
				title: event.value.title,
				short_description: event.value.short_description || '',
				description: event.value.description || '',
				start_date: event.value.start_date,
				end_date: event.value.end_date || event.value.start_date,
				start_time: event.value.start_time || null,
				end_time: event.value.end_time || null,
				location: event.value.location || '',
				virtual_link: event.value.virtual_link || '',
				max_attendees: event.value.max_attendees || 0,
				additional_attendee_amount: event.value.additional_attendee_amount || 0,
				published: event.value.published ? 1 : 0,
			},
		})
		event.value = { ...event.value, ...updated }
		toast.success(__('Saved'))
	} catch (err) {
		toast.error(err.messages?.[0] || __('Save failed'))
	} finally {
		saving.value = false
	}
}

const confirmDelete = async () => {
	if (!confirm(__('Delete this event? Registrations will be removed too.'))) return
	try {
		await call('frappe.client.delete', {
			doctype: 'Community Event',
			name: event.value.name,
		})
		toast.success(__('Event deleted'))
		router.push({ name: 'CommunityEvents' })
	} catch (err) {
		toast.error(err.messages?.[0] || __('Delete failed'))
	}
}

const confirmDeleteReg = async (reg) => {
	if (!confirm(__('Delete registration for {0}?').replace('{0}', reg.guardian_name))) return
	try {
		await call('lms.lms.community_event.delete_community_event_registration', {
			name: reg.name,
		})
		toast.success(__('Registration deleted'))
		registrations.reload()
	} catch (err) {
		toast.error(err.messages?.[0] || __('Delete failed'))
	}
}

const statusTheme = (s) => {
	if (s === 'Confirmed') return 'green'
	if (s === 'Free') return 'blue'
	return 'orange'
}

const breadcrumbs = computed(() => [
	{ label: __('Community Events'), route: { name: 'CommunityEvents' } },
	{ label: event.value?.title || props.slug },
])

usePageMeta(() => ({
	title: event.value?.title || __('Community Event'),
	icon: brand.favicon,
}))
</script>
