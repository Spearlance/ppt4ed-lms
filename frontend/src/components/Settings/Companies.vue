<template>
    <div class="flex min-h-0 flex-col text-base">
        <div class="flex items-center justify-between">
            <div>
                <div class="text-xl font-semibold mb-2 text-ink-gray-9">
                    {{ __('Companies') }}
                </div>
                <div class="text-ink-gray-6 leading-5">
                    {{ __('Add new companies or manage existing company accounts') }}
                </div>
            </div>
            <Button @click="showAddCompany = true">
                <template #prefix>
                    <Plus class="size-4 stroke-1.5" />
                </template>
                {{ __('Add Company') }}
            </Button>
        </div>

        <div class="mt-8 pb-10">
            <FormControl
                v-model="search"
                :placeholder="__('Search companies...')"
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
                        v-for="company in filteredCompanies"
                        :key="company.name"
                        class="flex items-center justify-between py-3"
                    >
                        <div class="space-y-1">
                            <router-link
                                :to="{ name: 'CompanyAdmin', params: { companyName: company.name } }"
                                class="text-ink-gray-9 font-medium hover:text-ink-blue-3 hover:underline"
                            >
                                {{ company.company_name }}
                            </router-link>
                            <div class="text-sm text-ink-gray-5">
                                {{ company.member_count }} members
                                <span v-if="company.billing_email">
                                    &middot; {{ company.billing_email }}
                                </span>
                            </div>
                        </div>
                        <Badge
                            :theme="company.status === 'Active' ? 'green' : company.status === 'Suspended' ? 'orange' : 'red'"
                        >
                            {{ company.status }}
                        </Badge>
                    </li>
                </ul>
                <div v-if="!filteredCompanies.length && !companies.loading" class="text-center py-10 text-ink-gray-5">
                    {{ __('No companies found') }}
                </div>
            </div>
        </div>

        <AddCompanyModal v-model="showAddCompany" @created="companies.reload()" />
    </div>
</template>

<script setup lang="ts">
import { Badge, Button, createResource, FormControl } from 'frappe-ui'
import { ref, computed } from 'vue'
import { Plus, Search } from 'lucide-vue-next'
import AddCompanyModal from '@/components/Modals/AddCompanyModal.vue'

const search = ref('')
const showAddCompany = ref(false)

const companies = createResource({
    url: 'lms.lms.api.get_companies',
    auto: true,
})

const filteredCompanies = computed(() => {
    const list = companies.data || []
    if (!search.value) return list
    const q = search.value.toLowerCase()
    return list.filter((c: any) =>
        c.company_name.toLowerCase().includes(q) ||
        (c.billing_email || '').toLowerCase().includes(q)
    )
})
</script>
