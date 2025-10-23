import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DraftPmsComponent } from './draft-pms.component';

describe('DraftPmsComponent', () => {
  let component: DraftPmsComponent;
  let fixture: ComponentFixture<DraftPmsComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ DraftPmsComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DraftPmsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
