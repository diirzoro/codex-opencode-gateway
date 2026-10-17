from backend.scripts.diagnose_opencode_permissions_test import summarize


def test_validator_shape_excludes_all_values_messages_and_unknown_names():
    private='private-token-and-filename'
    result=summarize({'success':False,'error':{'name':'ZodError','issues':[
        {'code':'invalid_type','path':['query','directory'],'message':private,'input':private},
        {'code':private,'path':[private,0],'message':private}]},private:private})
    assert private not in str(result)
    assert result['category']=='ZodError'
    assert result['issues']==[{'code':'invalid_type','path':['query','directory']},
                              {'code':'[other]','path':['[other]','[other]']}]


def test_permission_list_is_counted_without_exposing_commands_or_ids():
    assert summarize([{'id':'private','patterns':['secret command']}])=={'shape':'list','count':1}


def test_malformed_error_cannot_escape_allowlist():
    for payload in [{'name':['private'],'error':'private','issues':'private'},
                    {'issues':[{'code':[],'path':'private'}]}]:
        assert 'private' not in str(summarize(payload))
