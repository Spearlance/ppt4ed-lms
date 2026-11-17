<template>
	<Dialog
		v-model="show"
		:options="{
			size: '3xl',
		}"
	>
		<template #body-header>
			<div class="flex items-center justify-between mb-5">
				<div class="text-2xl font-semibold leading-6 text-ink-gray-9">
					{{ __('Edit Profile') }}
				</div>
				<div class="space-x-2">
					<Badge v-if="isDirty" theme="orange">
						{{ __('Not Saved') }}
					</Badge>
					<div class="pb-5 float-right">
						<Button variant="solid" @click="saveProfile()">
							{{ __('Save') }}
						</Button>
					</div>
				</div>
			</div>
		</template>
		<template #body-content>
			<div class="text-base">
				<div
					v-if="!isOwnProfile"
					data-testid="editing-other-profile"
					class="mb-5 rounded-md bg-surface-amber-1 px-3 py-2 text-sm text-ink-amber-3"
				>
					{{
						__(
							'You are editing the profile of {0}. Changes are saved to their account.'
						).format(props.profile.data?.full_name || '')
					}}
				</div>
				<div class="grid grid-cols-2 gap-10">
					<div class="space-y-4">
						<div class="space-y-4">
							<Uploader
								v-model="profile.image"
								:label="__('Profile Image')"
								:required="false"
								shape="circle"
							/>

							<FormControl
								v-model="profile.first_name"
								:label="__('First Name')"
								:required="true"
							/>
							<FormControl
								v-model="profile.last_name"
								:label="__('Last Name')"
								:required="true"
							/>
							<FormControl v-model="profile.headline" :label="__('Headline')" />
							<FormControl
								v-model="profile.mobile_no"
								type="tel"
								:label="__('Phone')"
							/>

							<FormControl
								v-model="profile.linkedin"
								:label="__('LinkedIn ID')"
							/>
							<FormControl v-model="profile.github" :label="__('GitHub ID')" />
							<FormControl
								v-model="profile.twitter"
								:label="__('Twitter ID')"
							/>
						</div>
					</div>
					<div class="space-y-4">
						<Link
							:label="__('Language')"
							v-model="profile.language"
							doctype="Language"
						/>
						<FormControl
							v-model="profile.license_type"
							type="select"
							:label="__('License Type')"
							:options="licenseTypeOptions"
							:description="
								__(
									'Used on CEU certificates. Required to issue CEU credit for licensed professionals.'
								)
							"
						/>
						<div class="grid grid-cols-3 gap-3">
							<FormControl
								v-model="profile.license_state"
								:label="__('License State')"
								placeholder="FL"
								class="col-span-1"
							/>
							<FormControl
								v-model="profile.professional_license_number"
								:label="__('License Number')"
								class="col-span-2"
							/>
						</div>
						<FormControl
							v-model="profile.signature_text"
							:label="__('Signature')"
							:description="
								__(
									'Rendered in cursive script on certificates when you are listed as a course instructor. Defaults to your full name when blank.'
								)
							"
						/>
						<FormControl
							v-model="profile.credentials"
							:label="__('Credentials')"
							placeholder="PT, DPT"
							:description="
								__(
									'Printed after your name on certificates you sign when the course has Show Signer Credentials turned on.'
								)
							"
						/>
						<FormControl
							v-model="profile.notification_audience"
							type="select"
							:label="__('Notification Audience')"
							:options="notificationAudienceOptions"
							:description="
								__(
									'Filter notifications about new courses and events to your audience. Leave on \'All audiences\' to receive everything.'
								)
							"
						/>
						<div>
							<div class="mb-1.5 text-sm text-ink-gray-5">
								{{ __('Bio') }}
							</div>
							<TextEditor
								:fixedMenu="true"
								@change="(val) => (profile.bio = val)"
								:content="profile.bio"
								:rows="15"
								editorClass="prose-sm py-2 px-2 min-h-[280px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
							/>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Badge,
	Button,
	createResource,
	Dialog,
	FormControl,
	TextEditor,
	toast,
} from 'frappe-ui'
import { computed, ref, reactive, watch } from 'vue'
import { sanitizeHTML } from '@/utils'
import { usersStore } from '@/stores/user'
import Link from '@/components/Controls/Link.vue'

const show = defineModel()
const reloadProfile = defineModel('reloadProfile')
const hasLanguageChanged = ref(false)
const isDirty = ref(false)
const { userResource } = usersStore()

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

// Admins can open this dialog on someone else's profile.
const isOwnProfile = computed(
	() =>
		!props.profile.data?.name ||
		userResource.data?.email === props.profile.data.name
)

const profile = reactive({
	first_name: '',
	last_name: '',
	headline: '',
	bio: '',
	image: '',
	linkedin: '',
	github: '',
	twitter: '',
	mobile_no: '',
	professional_license_number: '',
	license_type: '',
	license_state: '',
	signature_text: '',
	credentials: '',
	notification_audience: '',
})

const licenseTypeOptions = [
	{ label: __('— None —'), value: '' },
	{ label: 'OT', value: 'OT' },
	{ label: 'PT', value: 'PT' },
	{ label: 'SLP', value: 'SLP' },
	{ label: __('Other'), value: 'Other' },
]

const notificationAudienceOptions = [
	{ label: __('All audiences'), value: '' },
	{
		label: __('Healthcare Professionals'),
		value: 'Healthcare Professionals',
	},
	{ label: __('Educators'), value: 'Educators' },
	{ label: __('Parents / Caregivers'), value: 'Parents / Caregivers' },
]

const updateProfile = createResource({
	url: 'lms.lms.profile.update_profile',
	makeParams() {
		const { image, ...fields } = profile
		return {
			user: props.profile.data.name,
			fields: { ...fields, user_image: image || '' },
		}
	},
})

const validateMandatoryFields = () => {
	let missingFields = []
	if (!profile.first_name) missingFields.push(__('First Name'))
	if (!profile.last_name) missingFields.push(__('Last Name'))
	if (missingFields.length) {
		toast.error(
			__('Please fill the mandatory fields: {0}').format(
				missingFields.join(', ')
			)
		)
		console.error('Missing mandatory fields:', missingFields)
	}
	return missingFields.length
}

const saveProfile = () => {
	let missingMandatoryFields = validateMandatoryFields()
	if (missingMandatoryFields) return
	profile.bio = sanitizeHTML(profile.bio)
	updateProfile.submit(
		{},
		{
			onSuccess() {
				show.value = false
				reloadProfile.value.reload()
				toast.success(__('Profile saved'))
				// A language change only affects the page for the person it belongs to.
				const reloadPage = hasLanguageChanged.value && isOwnProfile.value
				hasLanguageChanged.value = false
				if (reloadPage) window.location.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}

// An empty field is null on the server and '' in the form, and the editor
// turns an empty bio into an empty paragraph. None of those is an edit.
const normalize = (key, value) => {
	const text = value == null ? '' : String(value)
	if (key === 'bio' && !text.replace(/<[^>]*>/g, '').trim()) return ''
	return text
}
const sameValue = (key, a, b) => normalize(key, a) === normalize(key, b)

watch(
	() => profile,
	(newVal) => {
		if (!props.profile.data) return
		let keys = Object.keys(newVal)
		keys.splice(keys.indexOf('image'), 1)
		for (let key of keys) {
			if (!sameValue(key, newVal[key], props.profile.data[key])) {
				isDirty.value = true
				return
			}
		}
		if (!sameValue('image', profile.image, props.profile.data.user_image)) {
			isDirty.value = true
			return
		}
		isDirty.value = false
	},
	{ deep: true }
)

watch(
	() => props.profile.data,
	(newVal) => {
		if (newVal) {
			profile.first_name = newVal.first_name
			profile.last_name = newVal.last_name
			profile.headline = newVal.headline
			profile.language = newVal.language
			profile.bio = newVal.bio
			profile.linkedin = newVal.linkedin
			profile.github = newVal.github
			profile.twitter = newVal.twitter
			profile.mobile_no = newVal.mobile_no || ''
			profile.professional_license_number =
				newVal.professional_license_number || ''
			profile.license_type = newVal.license_type || ''
			profile.license_state = newVal.license_state || ''
			profile.signature_text = newVal.signature_text || ''
			profile.credentials = newVal.credentials || ''
			profile.notification_audience = newVal.notification_audience || ''
			profile.image = newVal.user_image
			isDirty.value = false
		}
	}
)

watch(
	() => profile.language,
	() => {
		if (profile.language !== props.profile.data.language) {
			hasLanguageChanged.value = true
		}
	}
)
</script>
