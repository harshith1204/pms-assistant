import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ProjectPmsComponent } from './project-pms.component';

describe('ProjectPmsComponent', () => {
  let component: ProjectPmsComponent;
  let fixture: ComponentFixture<ProjectPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ProjectPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ProjectPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
