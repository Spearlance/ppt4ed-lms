<template>
	<div class="pl-5">
		<div class="grid grid-cols-1 md:grid-cols-[70%,30%]">
			<div
				v-if="courseResource.doc"
				class="lg:max-h-[88vh] lg:overflow-y-auto px-1"
			>
				<div class="my-5">
					<div class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b">
						<div class="text-lg font-semibold mb-4 text-ink-gray-9">
							{{ __('Details') }}
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<FormControl
								v-model="courseResource.doc.title"
								:label="__('Title')"
								:required="true"
								@input="makeFormDirty()"
							/>
							<CategoryMultiPicker
								v-model="courseResource.doc.categories"
								:label="__('Categories')"
								:allowCreate="true"
								:hint="__('Pick one or more categories. Manage the folder structure at /lms/admin-categories')"
								@update:modelValue="makeFormDirty()"
							/>
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<MultiSelect
								v-model="instructors"
								doctype="User"
								:label="__('Instructors')"
								url="lms.lms.api.search_users_by_role"
								:searchParams="{
									roles: JSON.stringify(['Moderator', 'LMS Student']),
								}"
								:onCreate="
									() => {
										showMemberModal = true
									}
								"
								:required="true"
								@update:modelValue="makeFormDirty()"
							/>
							<div>
								<label class="block mb-1 text-xs text-ink-gray-5">
									{{ __('Tags') }}
								</label>
								<div
									class="flex flex-wrap items-center gap-1.5 w-full rounded-lg border border-[--surface-gray-2] bg-surface-gray-2 px-2 py-1.5 cursor-text transition-colors focus-within:bg-surface-white focus-within:border-outline-gray-4 focus-within:shadow-sm focus-within:ring-0 focus-within:ring-2 focus-within:ring-outline-gray-3"
									@click="$refs.tagInput?.focus()"
								>
									<button
										v-for="tag in parsedTags"
										:key="tag"
										class="inline-flex items-center gap-1 bg-surface-white border border-outline-gray-2 text-ink-gray-7 pl-2 pr-1.5 py-0.5 rounded text-base leading-5"
										@click.stop="removeTag(tag)"
									>
										<span>{{ tag }}</span>
										<X class="size-3.5 stroke-1.5 shrink-0" />
									</button>
									<input
										id="tags"
										ref="tagInput"
										v-model="newTag"
										type="text"
										:placeholder="
											!parsedTags.length
												? __('Add a keyword and press enter')
												: ''
										"
										class="flex-1 min-w-[4rem] border-none outline-none bg-transparent p-0 text-base focus:ring-0"
										@keyup.enter="updateTags()"
									/>
								</div>
							</div>
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<Uploader
								v-model="courseResource.doc.image"
								:label="isResource ? __('Resource Image') : __('Course Image')"
								:required="false"
								@update:modelValue="makeFormDirty()"
							/>

							<ColorSwatches
								v-model="courseResource.doc.card_gradient"
								:label="__('Color')"
								:description="
									__(
										'Select a fallback color for the card when no image is set.'
									)
								"
								class="w-full"
								@update:modelValue="makeFormDirty()"
							/>
						</div>
					</div>

					<div
						v-if="isResource"
						class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b"
					>
						<div class="text-lg font-semibold text-ink-gray-9">
							{{ __('Resource Settings') }}
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<FormControl
								v-model="courseResource.doc.resource_type"
								:label="__('Resource Type')"
								type="select"
								:options="[
									{ label: __('Video'), value: 'Video' },
									{ label: __('Download'), value: 'Download' },
									{ label: __('Article'), value: 'Article' },
									{ label: __('Mini-Course'), value: 'Mini-Course' },
									{ label: __('Template'), value: 'Template' },
								]"
								@change="makeFormDirty()"
							/>
							<FormControl
								v-model="courseResource.doc.audience"
								:label="__('Audience')"
								type="select"
								:options="[
									{ label: __('— Not set —'), value: '' },
									{ label: __('Healthcare Professionals'), value: 'Healthcare Professionals' },
									{ label: __('Educators'), value: 'Educators' },
									{ label: __('Parents / Caregivers'), value: 'Parents / Caregivers' },
								]"
								:description="__('Determines which tab this resource appears under on the Resources page.')"
								@change="makeFormDirty()"
							/>
						</div>
					</div>

					<div class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b">
						<div class="text-lg font-semibold text-ink-gray-9">
							{{ __('Publishing Settings') }}
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<div
								v-if="user.data?.is_moderator"
								class="flex flex-col space-y-5"
							>
								<Switch
									size="sm"
									v-model="courseResource.doc.published"
									:label="__('Published')"
									:description="
										isResource
											? __('Make the resource visible to all users.')
											: __('Make the course visible to all users.')
									"
									@change="makeFormDirty()"
								/>
								<FormControl
									v-model="courseResource.doc.published_on"
									:label="__('Published On')"
									type="date"
									@change="makeFormDirty()"
								/>
							</div>
							<div class="flex flex-col space-y-5">
								<Switch
									size="sm"
									v-model="courseResource.doc.upcoming"
									:label="__('Upcoming')"
									:description="
										__(
											'Mark the course as upcoming but not yet open for enrollment.'
										)
									"
									@change="makeFormDirty()"
								/>
								<Switch
									size="sm"
									v-model="courseResource.doc.featured"
									:label="__('Featured')"
									:description="__('Highlight the course on the homepage.')"
									@change="makeFormDirty()"
								/>
								<Switch
									size="sm"
									v-model="selfEnrollment"
									:label="__('Allow Self Enrollment')"
									:description="
										__('Allow users to enroll in this course on their own.')
									"
								/>
							</div>
						</div>
					</div>

					<div class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b">
						<div class="text-lg font-semibold text-ink-gray-9">
							{{ isResource ? __('About the Resource') : __('About the Course') }}
						</div>
						<FormControl
							v-model="courseResource.doc.short_introduction"
							type="textarea"
							:rows="5"
							:label="__('Short Introduction')"
							:placeholder="
								isResource
									? __('A one line introduction shown on the resource card')
									: __(
										'A one line introduction to the course that appears on the course card'
									)
							"
							:required="true"
							@change="makeFormDirty()"
						/>
						<div class="">
							<div class="mb-1.5 text-sm text-ink-gray-5">
								{{ isResource ? __('Resource Description') : __('Course Description') }}
								<span class="text-ink-red-3">*</span>
							</div>
							<TextEditor
								:content="courseResource.doc.description"
								@change="
									(val) => {
										courseResource.doc.description = val
										makeFormDirty()
									}
								"
								:editable="true"
								:fixedMenu="true"
								editorClass="prose-sm max-w-none border-b border-x border-outline-gray-modals bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
							/>
						</div>

						<FormControl
							v-if="!isResource"
							v-model="courseResource.doc.video_link"
							:label="__('Preview Video')"
							:description="
								__(
									'Paste a YouTube link of a short video introducing the course.'
								)
							"
							@input="makeFormDirty()"
						/>

						<MultiSelect
							v-if="!isResource"
							v-model="related_courses"
							doctype="LMS Course"
							:label="__('Related Courses')"
							:filters="{ name: ['!=', courseResource.doc?.name] }"
							:onCreate="
								(close) => {
									router.push({
										name: 'Courses',
										query: { newCourse: '1' },
									})
								}
							"
							@update:modelValue="makeFormDirty()"
						/>
					</div>

					<div
						v-if="!isResource"
						class="pr-5 md:pr-10 pb-5 space-y-5 border-b"
					>
						<div class="text-lg font-semibold mt-5 text-ink-gray-9">
							{{ __('Pricing and Certification') }}
						</div>
						<div class="grid grid-cols-1 md:grid-cols-3 gap-5">
							<Switch
								size="sm"
								v-model="courseResource.doc.paid_course"
								:label="__('Paid Course')"
								:description="__('Charge a fee for course access.')"
								@change="makeFormDirty()"
							/>
							<Switch
								size="sm"
								v-model="courseResource.doc.enable_certification"
								:label="__('Completion Certificate')"
								:description="__('Issue a certificate on course completion.')"
								@change="makeFormDirty()"
							/>
						</div>
						<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
							<FormControl
								v-model="courseResource.doc.ceu_hours"
								type="number"
								:label="__('Credit Hours')"
								:description="__('CEU hours deducted from credit balance on enrollment.')"
								@input="makeFormDirty()"
							/>
							<div
								v-if="courseResource.doc.paid_course"
								class="space-y-5"
							>
								<FormControl
									v-model="courseResource.doc.course_price"
									:label="__('Amount')"
									@input="makeFormDirty()"
								/>
								<Link
									doctype="Currency"
									v-model="courseResource.doc.currency"
									:filters="{ enabled: 1 }"
									:label="__('Currency')"
									:required="courseResource.doc.paid_course"
									@update:modelValue="makeFormDirty()"
								/>
							</div>
						</div>
					</div>

					<div class="pr-5 md:pr-10 pb-5 space-y-5">
						<div class="text-lg font-semibold mt-5 text-ink-gray-9">
							{{ __('Meta Tags') }}
						</div>
						<div class="space-y-5">
							<FormControl
								v-model="meta.description"
								:label="__('Meta Description')"
								type="textarea"
								:rows="7"
								@input="makeFormDirty()"
							/>
							<FormControl
								v-model="meta.keywords"
								:label="__('Meta Keywords')"
								type="textarea"
								:rows="7"
								:placeholder="__('Comma separated keywords for SEO')"
								@input="makeFormDirty()"
							/>
						</div>
					</div>
				</div>
			</div>
			<div class="min-h-0 border-l">
				<CourseOutline
					v-if="courseResource.doc"
					:courseName="courseResource.doc.name"
					:title="__('Chapters')"
					:allowEdit="true"
				/>
			</div>
		</div>
	</div>
	<NewMemberModal
		v-model="showMemberModal"
		:defaultRoles="memberModalRoles"
		@created="onMemberCreated"
	/>
</template>
<script setup>
import {
	TextEditor,
	Switch,
	createResource,
	createDocumentResource,
	FormControl,
	usePageMeta,
	toast,
} from 'frappe-ui'
import {
	computed,
	inject,
	onMounted,
	onBeforeUnmount,
	ref,
	reactive,
	watch,
	getCurrentInstance,
} from 'vue'
import {
	getMetaInfo,
	sanitizeHTML,
	updateMetaInfo,
} from '@/utils'
import { X } from 'lucide-vue-next'
import { useRouter } from 'vue-router'
import Link from '@/components/Controls/Link.vue'
import CategoryMultiPicker from '@/components/Controls/CategoryMultiPicker.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import MultiSelect from '@/components/Controls/MultiSelect.vue'
import ColorSwatches from '@/components/Controls/ColorSwatches.vue'
import Uploader from '@/components/Controls/Uploader.vue'
import NewMemberModal from '@/components/Modals/NewMemberModal.vue'

const user = inject('$user')
const newTag = ref('')
const router = useRouter()
const instructors = ref([])
const related_courses = ref([])
const app = getCurrentInstance()
const { $dialog } = app.appContext.config.globalProperties
const isDirty = ref(false)
const showMemberModal = ref(false)

const selfEnrollment = computed({
	get: () => !courseResource.doc?.disable_self_learning,
	set: (val) => {
		courseResource.doc.disable_self_learning = !val
		makeFormDirty()
	},
})

const isResource = computed(
	() => courseResource.doc?.course_type === 'Resource'
)
const memberModalRoles = ref(['moderator'])

const props = defineProps({
	course: {
		type: Object,
	},
})

const meta = reactive({
	description: '',
	keywords: '',
})

onMounted(() => {
	if (!user.data?.is_moderator) {
		router.push({ name: 'Courses' })
	}
	window.addEventListener('keydown', keyboardShortcut)
})

const courseResource = createDocumentResource({
	doctype: 'LMS Course',
	name: props.course.data?.name,
	auto: true,
})

const parsedTags = computed(() => {
	const tags = courseResource.doc?.tags
	return tags ? tags.split(', ').filter(Boolean) : []
})

watch(
	() => courseResource.doc,
	() => {
		getMetaInfo('courses', courseResource.doc?.name, meta)
		updateCourseData()
		checkPermission()
	}
)

const updateCourseData = () => {
	Object.keys(courseResource.doc).forEach((key) => {
		if (key == 'instructors') {
			instructors.value = []
			courseResource.doc.instructors.forEach((instructor) => {
				instructors.value.push(instructor.instructor)
			})
		} else if (key == 'related_courses') {
			related_courses.value = []
			courseResource.doc.related_courses.forEach((course) => {
				related_courses.value.push(course.course)
			})
		}
	})
	let checkboxes = [
		'published',
		'upcoming',
		'disable_self_learning',
		'paid_course',
		'featured',
		'enable_certification',
	]
	for (let idx in checkboxes) {
		let key = checkboxes[idx]
		courseResource.doc[key] = courseResource.doc[key] ? true : false
	}
}

const submitCourse = () => {
	validateFields()
	updateCourse()
}

const onMemberCreated = (user) => {
	instructors.value = [...instructors.value, user.name]
}

const validateFields = () => {
	Object.keys(courseResource.doc).forEach((key) => {
		if (typeof courseResource.doc[key] === 'string') {
			courseResource.doc[key] = sanitizeHTML(courseResource.doc[key])
		}
	})
}

const updateCourse = () => {
	courseResource.setValue.submit(
		{
			...courseResource.doc,
			instructors: instructors.value.map((instructor) => ({
				instructor: instructor,
			})),
			related_courses: related_courses.value.map((course) => ({
				course: course,
			})),
		},
		{
			onSuccess() {
				updateMetaInfo('courses', courseResource.doc?.name, meta)
				toast.success(
					isResource.value
						? __('Resource updated successfully')
						: __('Course updated successfully')
				)
				isDirty.value = false
				courseResource.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
				console.error(err)
			},
		}
	)
}

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		submitCourse()
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	window.removeEventListener('keydown', keyboardShortcut)
})

const deleteCourse = createResource({
	url: 'lms.lms.api.delete_course',
	makeParams(values) {
		return {
			course: courseResource.doc?.name,
		}
	},
	onSuccess() {
		toast.success(
			isResource.value
				? __('Resource deleted successfully')
				: __('Course deleted successfully')
		)
		router.push({ name: isResource.value ? 'Resources' : 'Courses' })
	},
})

const trashCourse = () => {
	$dialog({
		title: isResource.value ? __('Delete Resource') : __('Delete Course'),
		message: isResource.value
			? __(
					'Deleting the resource will also delete all its chapters and lessons. Are you sure you want to delete this resource?'
				)
			: __(
					'Deleting the course will also delete all its chapters and lessons. Are you sure you want to delete this course?'
				),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteCourse.submit()
					close()
				},
			},
		],
	})
}

const updateTags = () => {
	if (newTag.value) {
		courseResource.doc.tags = courseResource.doc.tags
			? `${courseResource.doc.tags}, ${newTag.value}`
			: newTag.value
		newTag.value = ''
		makeFormDirty()
	}
}

const removeTag = (tag) => {
	courseResource.doc.tags = courseResource.doc.tags
		?.split(', ')
		.filter((t) => t !== tag)
		.join(', ')
	newTag.value = ''
	makeFormDirty()
}

const checkPermission = () => {
	let user_is_instructor = false
	if (user.data?.is_moderator) return
	instructors.value?.forEach((instructor) => {
		if (!user_is_instructor && instructor == user.data?.name) {
			user_is_instructor = true
		}
	})

	if (!user_is_instructor) {
		router.push({ name: 'Courses' })
	}
}

const makeFormDirty = () => {
	isDirty.value = true
}

defineExpose({
	submitCourse,
	trashCourse,
	isDirty,
})
</script>
