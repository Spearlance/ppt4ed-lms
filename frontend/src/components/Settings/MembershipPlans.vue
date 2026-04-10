<template>
    <div class="flex min-h-0 flex-col text-base">
        <div class="flex items-center justify-between">
            <div>
                <div class="text-xl font-semibold mb-2 text-ink-gray-9">
                    {{ __('Membership Plans') }}
                </div>
                <div class="text-ink-gray-6 leading-5">
                    {{ __('Create and manage membership plans with Stripe pricing') }}
                </div>
            </div>
            <Button @click="startCreate">
                <template #prefix>
                    <Plus class="size-4 stroke-1.5" />
                </template>
                {{ __('Add Plan') }}
            </Button>
        </div>

        <div class="mt-8 pb-10">
            <FormControl
                v-model="search"
                :placeholder="__('Search plans...')"
                type="text"
                :debounce="300"
                class="w-1/4 mb-4"
            >
                <template #prefix>
                    <Search class="size-4 stroke-1.5 text-ink-gray-5" />
                </template>
            </FormControl>

            <div class="overflow-y-auto max-h-[60vh]">
                <ul class="divide-y divide-outline-gray-modals">
                    <li
                        v-for="plan in filteredPlans"
                        :key="plan.name"
                        class="py-3"
                    >
                        <!-- View mode -->
                        <div
                            v-if="editing !== plan.name"
                            class="flex items-center justify-between cursor-pointer hover:bg-surface-gray-2 -mx-2 px-2 rounded"
                            @click="startEdit(plan)"
                        >
                            <div class="space-y-1">
                                <div class="text-ink-gray-9 font-medium">
                                    {{ plan.title }}
                                </div>
                                <div class="text-sm text-ink-gray-5">
                                    {{ plan.plan_type }} &middot;
                                    ${{ Number(plan.price).toLocaleString() }}/year
                                    <span v-if="plan.ceu_hours">
                                        &middot; {{ plan.ceu_hours }} CEU hours
                                    </span>
                                </div>
                            </div>
                            <Badge :theme="plan.active ? 'green' : 'gray'">
                                {{ plan.active ? 'Active' : 'Inactive' }}
                            </Badge>
                        </div>

                        <!-- Edit mode -->
                        <div v-else class="bg-surface-gray-2 -mx-2 px-4 py-4 rounded space-y-4">
                            <div class="grid grid-cols-2 gap-4">
                                <FormControl
                                    v-model="editForm.title"
                                    :label="__('Title')"
                                    type="text"
                                />
                                <div>
                                    <label class="block text-xs text-ink-gray-5 mb-1.5">{{ __('Plan Type') }}</label>
                                    <select
                                        v-model="editForm.plan_type"
                                        class="w-full rounded border border-outline-gray-modals bg-surface-white px-2.5 py-1.5 text-base text-ink-gray-9"
                                    >
                                        <option value="Professional">Professional</option>
                                        <option value="Company">Company</option>
                                        <option value="Individual-Business">Individual-Business</option>
                                    </select>
                                </div>
                            </div>
                            <div class="grid grid-cols-3 gap-4">
                                <FormControl
                                    v-model="editForm.price"
                                    :label="__('Price (USD/year)')"
                                    type="number"
                                />
                                <FormControl
                                    v-model="editForm.ceu_hours"
                                    :label="__('CEU Hours')"
                                    type="number"
                                />
                                <FormControl
                                    v-model="editForm.stripe_price_id"
                                    :label="__('Stripe Price ID')"
                                    type="text"
                                />
                            </div>
                            <div class="grid grid-cols-2 gap-4">
                                <FormControl
                                    v-model="editForm.display_order"
                                    :label="__('Display Order')"
                                    type="number"
                                />
                            </div>
                            <div class="flex items-center justify-between">
                                <div class="flex items-center gap-4">
                                    <label class="flex items-center gap-2 text-sm text-ink-gray-7 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            v-model="editForm.active"
                                            :true-value="1"
                                            :false-value="0"
                                            class="rounded"
                                        />
                                        {{ __('Active') }}
                                    </label>
                                    <label class="flex items-center gap-2 text-sm text-ink-gray-7 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            v-model="editForm.is_recommended"
                                            :true-value="1"
                                            :false-value="0"
                                            class="rounded"
                                        />
                                        {{ __('Recommended') }}
                                    </label>
                                </div>
                                <div class="flex gap-2">
                                    <Button @click="cancelEdit">{{ __('Cancel') }}</Button>
                                    <Button variant="solid" :loading="saving" @click="saveEdit">
                                        {{ __('Save') }}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    </li>
                </ul>

                <div v-if="!filteredPlans.length && !plans.loading" class="text-center py-10 text-ink-gray-5">
                    {{ __('No plans found') }}
                </div>
            </div>
        </div>

        <!-- Create dialog -->
        <Dialog
            v-model="showCreate"
            :options="{
                title: __('New Membership Plan'),
                actions: [
                    {
                        label: __('Create Plan'),
                        variant: 'solid',
                        loading: creating,
                        onClick: ({ close }) => doCreate(close),
                    },
                ],
            }"
        >
            <template #body-content>
                <div class="space-y-4">
                    <FormControl
                        v-model="createForm.title"
                        :label="__('Title')"
                        type="text"
                        :required="true"
                    />
                    <div>
                        <label class="block text-xs text-ink-gray-5 mb-1.5">{{ __('Plan Type') }}</label>
                        <select
                            v-model="createForm.plan_type"
                            class="w-full rounded border border-outline-gray-modals bg-surface-white px-2.5 py-1.5 text-base text-ink-gray-9"
                        >
                            <option value="Professional">Professional</option>
                            <option value="Company">Company</option>
                            <option value="Individual-Business">Individual-Business</option>
                        </select>
                    </div>
                    <div class="grid grid-cols-2 gap-4">
                        <FormControl
                            v-model="createForm.price"
                            :label="__('Price (USD/year)')"
                            type="number"
                            :required="true"
                        />
                        <FormControl
                            v-model="createForm.ceu_hours"
                            :label="__('CEU Hours')"
                            type="number"
                        />
                    </div>
                    <FormControl
                        v-model="createForm.stripe_price_id"
                        :label="__('Stripe Price ID')"
                        type="text"
                    />
                </div>
            </template>
        </Dialog>
    </div>
</template>

<script setup>
import { Badge, Button, Dialog, FormControl, call, toast } from 'frappe-ui'
import { ref, computed, reactive } from 'vue'
import { Plus, Search } from 'lucide-vue-next'

const search = ref('')
const editing = ref(null)
const saving = ref(false)
const creating = ref(false)
const showCreate = ref(false)

const editForm = reactive({
    title: '',
    plan_type: '',
    price: 0,
    ceu_hours: 0,
    stripe_price_id: '',
    active: 1,
    display_order: 0,
    is_recommended: 0,
})

const createForm = reactive({
    title: '',
    plan_type: 'Professional',
    price: 0,
    ceu_hours: 0,
    stripe_price_id: '',
})

const plans = ref({ data: [], loading: true })

const loadPlans = async () => {
    plans.value.loading = true
    try {
        plans.value.data = await call('lms.lms.api.get_all_membership_plans')
    } catch (err) {
        toast.error(err.messages?.[0] || 'Failed to load plans')
    }
    plans.value.loading = false
}

loadPlans()

const filteredPlans = computed(() => {
    const list = plans.value.data || []
    if (!search.value) return list
    const q = search.value.toLowerCase()
    return list.filter((p) =>
        p.title.toLowerCase().includes(q) ||
        p.plan_type.toLowerCase().includes(q)
    )
})

const startEdit = (plan) => {
    editing.value = plan.name
    Object.assign(editForm, {
        title: plan.title,
        plan_type: plan.plan_type,
        price: plan.price,
        ceu_hours: plan.ceu_hours,
        stripe_price_id: plan.stripe_price_id || '',
        active: plan.active,
        display_order: plan.display_order || 0,
        is_recommended: plan.is_recommended || 0,
    })
}

const cancelEdit = () => {
    editing.value = null
}

const saveEdit = async () => {
    saving.value = true
    try {
        await call('lms.lms.api.update_membership_plan', {
            plan_name: editing.value,
            title: editForm.title,
            plan_type: editForm.plan_type,
            price: editForm.price,
            ceu_hours: editForm.ceu_hours,
            stripe_price_id: editForm.stripe_price_id,
            active: editForm.active,
            display_order: editForm.display_order,
            is_recommended: editForm.is_recommended,
        })
        toast.success(__('Plan updated'))
        editing.value = null
        await loadPlans()
    } catch (err) {
        toast.error(err.messages?.[0] || 'Failed to update plan')
    }
    saving.value = false
}

const startCreate = () => {
    Object.assign(createForm, {
        title: '',
        plan_type: 'Professional',
        price: 0,
        ceu_hours: 0,
        stripe_price_id: '',
    })
    showCreate.value = true
}

const doCreate = async (close) => {
    if (!createForm.title?.trim()) {
        toast.error(__('Title is required'))
        return
    }
    if (!createForm.price) {
        toast.error(__('Price is required'))
        return
    }
    creating.value = true
    try {
        await call('lms.lms.api.create_membership_plan', {
            title: createForm.title,
            plan_type: createForm.plan_type,
            price: createForm.price,
            ceu_hours: createForm.ceu_hours,
            stripe_price_id: createForm.stripe_price_id,
        })
        toast.success(__('Plan created'))
        close?.()
        await loadPlans()
    } catch (err) {
        toast.error(err.messages?.[0] || 'Failed to create plan')
    }
    creating.value = false
}
</script>
