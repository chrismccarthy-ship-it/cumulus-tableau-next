/**
 * Server-side actions behind the Cumulus console dashboard extensions (Retail RVP / Wealth Advisor).
 * Every method is a small, auditable write the demo can show in the org: a Case, a Task, a calendar Event,
 * an e-mailed report. Flow launching is done client-side with lightning-flow; this class only lists the flows.
 */
public with sharing class CumulusConsoleActions {

    @AuraEnabled
    public static Id createCase(String subject, String description, String origin) {
        Case c = new Case(Subject = left(subject, 255), Description = description, Origin = String.isBlank(origin) ? 'Web' : origin, Priority = 'High', Status = 'New');
        insert c;
        return c.Id;
    }

    @AuraEnabled
    public static Id createTask(String subject, String description, Date dueDate) {
        Task t = new Task(Subject = left(subject, 255), Description = description, ActivityDate = dueDate == null ? Date.today().addDays(7) : dueDate, Priority = 'High', Status = 'Not Started', OwnerId = UserInfo.getUserId());
        insert t;
        return t.Id;
    }

    @AuraEnabled
    public static Id scheduleMeeting(String subject, String description, Date meetingDate, Integer durationMinutes, String attendees) {
        Datetime startDt = Datetime.newInstance(meetingDate == null ? Date.today() : meetingDate, Time.newInstance(10, 0, 0, 0));
        Event e = new Event(Subject = left(subject, 255), Description = (String.isBlank(attendees) ? '' : 'Attendees: ' + attendees + '\n\n') + description,
                            StartDateTime = startDt, DurationInMinutes = durationMinutes == null || durationMinutes <= 0 ? 30 : durationMinutes, OwnerId = UserInfo.getUserId());
        insert e;
        return e.Id;
    }

    @AuraEnabled
    public static String emailReport(String subject, String htmlBody) {
        Messaging.SingleEmailMessage m = new Messaging.SingleEmailMessage();
        m.setTargetObjectId(UserInfo.getUserId());
        m.setSaveAsActivity(false);
        m.setSubject(left(subject, 255));
        m.setHtmlBody(htmlBody);
        Messaging.sendEmail(new List<Messaging.SingleEmailMessage>{ m });
        return UserInfo.getUserEmail();
    }

    @AuraEnabled(cacheable=true)
    public static List<Map<String, String>> listScreenFlows() {
        List<Map<String, String>> out = new List<Map<String, String>>();
        for (FlowDefinitionView f : [SELECT ApiName, Label FROM FlowDefinitionView WHERE IsActive = true AND ProcessType = 'Flow' ORDER BY Label LIMIT 200]) {
            out.add(new Map<String, String>{ 'apiName' => f.ApiName, 'label' => f.Label });
        }
        return out;
    }

    private static String left(String s, Integer n) {
        return s == null ? '' : (s.length() > n ? s.substring(0, n) : s);
    }
}
