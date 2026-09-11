export const ALLOWED_CRUD_TABLES = [
  'incident',
  'change_request',
  'sys_req_item',
  'sys_script_include',
  'sys_script',
  'sys_script_client',
  'scan_table_check',
  'scan_column_type_check',
  'scan_linter_check',
  'scan_script_only_check',
  'scan_check_suite',
  'sys_atf_test',
  'sys_atf_step',
  'sys_atf_test_suite',
  'sys_atf_test_result',
  'sys_atf_step_result',
  'sys_variable_value'
];

export function isAllowedCrudTable(table) {
  return ALLOWED_CRUD_TABLES.includes(table);
}

export function formatAllowedCrudTables() {
  return ALLOWED_CRUD_TABLES.join(', ');
}